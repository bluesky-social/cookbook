import time
import sqlite3
from urllib.parse import urlparse, parse_qs, urlencode
from flask import Flask, flash, url_for, redirect, render_template, jsonify, request, g
from authlib.jose import JsonWebKey
from authlib.common.security import generate_token
from authlib.integrations.requests_client import OAuth2Session
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
        db_path = app.config.get("DATABASE_URL", "app.sqlite")
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
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
        "grant_types": ['authorization_code', 'implicit', 'refresh_token'], # XXX: implicit?
        # XXX: "response_types": ['code id_token', 'code'], # XXX:
        "response_types": ['code'],
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

    # fetch auth server metadata
    resp = requests.get(f"{authsrv_url}/.well-known/oauth-authorization-server")
    resp.raise_for_status()
    
    authsrv_meta = resp.json()
    print("Auth Server Metadata: " + json.dumps(authsrv_meta, indent=2))
    assert valid_authsrv_metadata(authsrv_meta, authsrv_url)

    par_url = authsrv_meta["pushed_authorization_request_endpoint"]
    issuer = authsrv_meta["issuer"]
    state = generate_token()
    nonce = generate_token()
    pkce_verifier = generate_token()
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
    dpop_jwk = JsonWebKey.generate_key("EC", "P-256", is_private=True).as_json(is_private=True)
    query_db("INSERT IN TO oauth_session (state, iss, nonce, pkce_verifier, dpop_private_jwk) VALUES(?, ?, ?, ?, ?);", [state, issuer, nonce, pkce_verifier, dpop_private_jwk])

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
    args = request.args()
    print(args)
    row = query_db("SELECT * FROM oauth_session WHERE state = ?;", [args["state"]], one=True)
    if row is None:
        raise Exception("OAuth session not found")

    # delete row to prevent replay
    query_db("DELETE * FROM oauth_session WHERE state = ?;", [args["state"]])

    # construct token request
    #grant_type=authorization_code
    #code=args["code"],
    #code_verifier=row["pkce_verifier"],
    #client_id=bsky.app
    #redirect_uri=https://bsky.app/my-app/oauth-callback
    #client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer
    #client_assertion=<SELF_SIGNED_JWT>

    # expected response
    #"access_token": "Kz~8mXK1EalYznwH-LC-1fBAo.4Ljp~zsPE_NeO.gxU",
    #"token_type": "DPoP",
    #"expires_in": 2677,
    #"refresh_token": "Q..Zkm29lexi8VnWg2zPW1x-tgGad0Ibc3s3EwM_Ni4-g"


    # do something here?

    return redirect('/')

@app.route('/post')
def bsky_post():
    return render_template('post.html')
