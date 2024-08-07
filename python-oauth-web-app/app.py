import time
import sqlite3
import functools
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode
from flask import Flask, flash, url_for, redirect, render_template, jsonify, request, g, session
from authlib.jose import JsonWebKey
from authlib.common.security import generate_token
from authlib.jose import jwt
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from atproto_identity import *
from atproto_oauth import *

app = Flask(__name__)
app.config.from_prefixed_env()

secret_jwk = JsonWebKey.import_key(app.config["SECRET_JWK"])
pub_jwk = json.loads(secret_jwk.as_json(is_private=False))
assert 'd' not in pub_jwk

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db_path = app.config.get("DATABASE_URL", "demo.sqlite")
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    print("initializing database...")
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

init_db()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.before_request
def load_logged_in_user():
    user_did = session.get('user_did')

    if user_did is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM oauth_session WHERE did = ?', (user_did,)
        ).fetchone()

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect("/oauth/login")

        return view(**kwargs)

    return wrapped_view

@app.route('/')
def homepage():
    return render_template('home.html')

@app.route('/oauth/client-metadata.json')
def oauth_client_metadata():
    client_id = request.base_url.replace("http://", "https://")
    url_root = request.url_root.replace("http://", "https://")
    return jsonify({
        # simply using the full request URL for the client_id
        "client_id": client_id,
        "dpop_bound_access_tokens": True,
        "application_type": "web",
        "redirect_uris": [f"{url_root}oauth/authorize"],
        "client_uri": url_root,
        "subject_type": "public",
        "grant_types": ['authorization_code', 'refresh_token'], # TODO: implicit?
        "response_types": ['code'], # TODO: "code id_token"?
        "scope": 'openid profile offline_access',
        "client_name": 'atproto OAuth Flask Backend Demo',
        "token_endpoint_auth_method": 'none',
        "jwks_uri": f"{url_root}oauth/jwks.json",
        #"jwks": { #    "keys": [pub_jwk], #},
    })

@app.route('/oauth/jwks.json')
def oauth_jwks():
    return jsonify({
        "keys": [pub_jwk],
    })

@app.route('/oauth/login', methods=('GET', 'POST'))
def oauth_login():
    if request.method != "POST":
        return render_template('login.html')

    # resolve handle and DID document
    username = request.form['username']
    if not valid_handle(username):
        flash("Invalid Handle")
        return redirect("/oauth/login")
    did = resolve_handle(username)
    if not valid_did(did):
        flash("Invalid DID")
        return redirect("/oauth/login")
    did_doc = resolve_did(did)
    pds_url = pds_endpoint(did_doc)

    # TODO: validate that pds_url is safe before doing request!
    print(f"PDS: {pds_url}")

    # fetch PDS metadata
    resp = requests.get(f"{pds_url}/.well-known/oauth-protected-resource")
    resp.raise_for_status()
    authsrv_url = resp.json()["authorization_servers"][0]

    # TODO: validate that authsrv_url is safe before doing request!
    print(f"Auth Server: {authsrv_url}")

    authsrv_meta = fetch_authsrv_meta(authsrv_url)

    par_url = authsrv_meta["pushed_authorization_request_endpoint"]
    issuer = authsrv_meta["issuer"]
    state = generate_token()
    nonce = generate_token()
    pkce_verifier = generate_token(48)
    url_root = request.url_root.replace("http://", "https://")
    redirect_uri = f"{url_root}oauth/authorize"
    client_id = f"{url_root}oauth/client-metadata.json"
    scope = "openid profile offline_access"

    # generate PKCE code_challenge, and use it for PAR request
    code_challenge = create_s256_code_challenge(pkce_verifier)
    code_challenge_method = "S256"

    # self-signed JWT using the private key declared in client metadata JWKS
    client_assertion = jwt.encode(
        {'alg': 'ES256', 'kid': secret_jwk['kid']},
        {'iss': client_id, 'sub': client_id, 'aud': authsrv_url, 'jti': generate_token(), 'iat': int(time.time())},
        secret_jwk,
    ).decode('utf-8')

    par_body = {
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "client_id": client_id,
        "state": state,
        "nonce": nonce,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "login_hint": did,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }
    print(par_body)
    resp = requests.post(
        par_url,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data=par_body,
    )
    print(resp.json())
    resp.raise_for_status()
    request_uri = resp.json()["request_uri"]

    # persist session state to database
    dpop_private_jwk = JsonWebKey.generate_key("EC", "P-256", is_private=True).as_json(is_private=True)
    print(f"saving oauth_request to DB: {state}")
    query_db("INSERT INTO oauth_request (state, iss, nonce, pkce_verifier, dpop_private_jwk, did, handle, pds_url) VALUES(?, ?, ?, ?, ?, ?, ?, ?);", [state, issuer, nonce, pkce_verifier, dpop_private_jwk, did, username, pds_url])

    # TODO: check that this is safe URL
    auth_url = authsrv_meta["authorization_endpoint"]
    qparam = urlencode({"client_id": client_id, "request_uri": request_uri})
    return redirect(f"{auth_url}?{qparam}")

@app.route('/oauth/logout')
def oauth_logout():
    session.clear()
    return redirect("/")

@app.route('/oauth/authorize')
def oauth_authorize():
    print(request.args)
    row = query_db("SELECT * FROM oauth_request WHERE state = ?;", [request.args["state"]], one=True)
    if row is None:
        raise Exception("OAuth request not found")

    dpop_key = JsonWebKey.import_key(json.loads(row["dpop_private_jwk"]))
    dpop_pub_jwk = json.loads(dpop_key.as_json(is_private=False))

    # delete row to prevent replay
    # XXX:
    #query_db("DELETE * FROM oauth_request WHERE state = ?;", [request.args["state"]])

    # fetch server metadata again
    authsrv_url = request.args["iss"]
    authsrv_meta = fetch_authsrv_meta(authsrv_url)

    # construct auth request
    url_root = request.url_root.replace("http://", "https://")
    client_id = f"{url_root}oauth/client-metadata.json"
    redirect_uri = f"{url_root}oauth/authorize"
    client_assertion = jwt.encode(
        {'alg': 'ES256', 'kid': secret_jwk['kid']},
        {'iss': client_id, 'sub': client_id, 'aud': authsrv_url, 'jti': generate_token(), 'iat': int(time.time())},
        secret_jwk,
    ).decode('utf-8')

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code": request.args["code"],
        "code_verifier": row["pkce_verifier"],
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }

    # create DPoP header JWT
    token_url = authsrv_meta["token_endpoint"]
    dpop_proof = jwt.encode(
        {'typ': 'dpop+jwt', 'alg': 'ES256', 'jwk': dpop_pub_jwk},
        {
            'jti': generate_token(),
            'htm': "POST",
            'htu': token_url,
            'iat': int(time.time()),
            'exp': int(time.time()) + 30,
        },
        dpop_key,
    ).decode('utf-8')

    print(params)
    # TODO: check if safe URL
    dpop_nonce = ""
    resp = requests.post(token_url, data=params, headers={"DPoP": dpop_proof})
    if resp.status_code == 400 and resp.json()['error'] == "use_dpop_nonce":
        #print(resp.headers)
        server_nonce = resp.headers["DPoP-Nonce"] # Dpop-Nonce
        #print(server_nonce)
        dpop_proof = jwt.encode(
            {'typ': 'dpop+jwt', 'alg': 'ES256', 'jwk': dpop_pub_jwk},
            {
                'jti': generate_token(),
                'htm': "POST",
                'htu': token_url,
                'nonce': server_nonce,
                'iat': int(time.time()),
                'exp': int(time.time()) + 30,
            },
            dpop_key,
        ).decode('utf-8')
        resp = requests.post(token_url, data=params, headers={"DPoP": dpop_proof})

    print(resp.json())
    resp.raise_for_status()


    token_body = resp.json()

    # validate against request DID
    assert token_body['sub'] == row["did"]

    query_db("INSERT INTO oauth_session (did, handle, pds_url, iss, access_token, refresh_token, dpop_nonce, dpop_private_jwk) VALUES(?, ?, ?, ?, ?, ?, ?, ?);", [row["did"], row["handle"], row["pds_url"], row["iss"], token_body["access_token"], token_body["refresh_token"], dpop_nonce, row["dpop_private_jwk"]])

    session['user_did'] = row["did"]

    return redirect('/')

@login_required
@app.route('/bsky/post', methods=('GET', 'POST'))
def bsky_post():
    if request.method != "POST":
        return render_template('bsky_post.html')

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pds_url = g.user["pds_url"]
    did = g.user["did"]
    req_url = f"{pds_url}/xrpc/com.atproto.repo.createRecord"

    dpop_key = JsonWebKey.import_key(json.loads(g.user["dpop_private_jwk"]))
    dpop_pub_jwk = json.loads(dpop_key.as_json(is_private=False))
    nonce = g.user["dpop_nonce"]
    access_token = g.user["access_token"]

    for i in range(2):
        print(f"access nonce: {nonce}")
        dpop_jwt = jwt.encode(
            {'typ': 'dpop+jwt', 'alg': 'ES256', 'jwk': dpop_pub_jwk},
            {
                'iss': g.user["iss"],
                'iat': int(time.time()),
                'exp': int(time.time()) + 10,
                'jti': generate_token(),
                'htm': "POST",
                'htu': req_url,
                'nonce': nonce,
                # this S256 is same as DPoP ath hashing
                'ath': create_s256_code_challenge(access_token),
            },
            dpop_key,
        ).decode('utf-8')

        resp = requests.post(req_url,
            headers={"Authorization": f"DPoP {access_token}", "DPoP": dpop_jwt},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": request.form["post_text"],
                    "createdAt": now,
                },
            },
        )
        if resp.status_code in [400, 401] and resp.json()['error'] == "use_dpop_nonce":
            #print(resp.headers)
            nonce = resp.headers["DPoP-Nonce"] # Dpop-Nonce
            # TODO: update database
            continue
        break
    print(resp.json())
    resp.raise_for_status()

    flash("Posted!")
    return render_template('bsky_post.html')
