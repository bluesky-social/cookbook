import time
import sqlite3
import functools
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode
from flask import (
    Flask,
    flash,
    url_for,
    redirect,
    render_template,
    jsonify,
    request,
    g,
    session,
    abort,
)
from authlib.jose import JsonWebKey
from authlib.common.security import generate_token
from authlib.jose import jwt
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from atproto_identity import *
from atproto_oauth import *
from atproto_security import is_safe_url, hardened_http

app = Flask(__name__)
app.config.from_prefixed_env()

secret_jwk = JsonWebKey.import_key(app.config["SECRET_JWK"])
pub_jwk = json.loads(secret_jwk.as_json(is_private=False))
assert "d" not in pub_jwk


def get_db():
    db = getattr(g, "_database", None)
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
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


init_db()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@app.before_request
def load_logged_in_user():
    user_did = session.get("user_did")

    if user_did is None:
        g.user = None
    else:
        g.user = (
            get_db()
            .execute("SELECT * FROM oauth_session WHERE did = ?", (user_did,))
            .fetchone()
        )


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect("/oauth/login")

        return view(**kwargs)

    return wrapped_view


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", status_code=500, err=e), 500


@app.errorhandler(400)
def bad_request_error(e):
    return render_template("error.html", status_code=400, err=e), 400


@app.route("/")
def homepage():
    return render_template("home.html")


@app.route("/oauth/client-metadata.json")
def oauth_client_metadata():
    app_url = request.url_root.replace("http://", "https://")
    client_id = f"{app_url}oauth/client-metadata.json"

    return jsonify(
        {
            # simply using the full request URL for the client_id
            "client_id": client_id,
            "dpop_bound_access_tokens": True,
            "application_type": "web",
            "redirect_uris": [f"{app_url}oauth/authorize"],
            "client_uri": app_url,
            "subject_type": "public",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],  # TODO: "code id_token"?
            "scope": "openid profile offline_access",
            "client_name": "atproto OAuth Flask Backend Demo",
            "token_endpoint_auth_method": "none",
            "jwks_uri": f"{app_url}oauth/jwks.json",
            # "jwks": { #    "keys": [pub_jwk], #},
        }
    )


@app.route("/oauth/jwks.json")
def oauth_jwks():
    return jsonify(
        {
            "keys": [pub_jwk],
        }
    )


@app.route("/oauth/login", methods=("GET", "POST"))
def oauth_login():
    if request.method != "POST":
        return render_template("login.html")

    # resolve handle and DID document, using atproto identity helpers
    username = request.form["username"]
    if not valid_handle(username):
        flash("Invalid Handle")
        return render_template("login.html"), 400
    did = resolve_handle(username)
    if not did:
        flash("Handle Not Found")
        return render_template("login.html"), 400
    if not valid_did(did):
        flash("Handle resolved to invalid DID")
        return render_template("login.html"), 400
    did_doc = resolve_did(did)
    if not did_doc:
        flash("DID Not Found: " + did)
        return render_template("login.html"), 400

    # fetch PDS OAuth metadata
    # IMPORTANT: PDS endpoint URL is untrusted input, SSRF mitigations are needed
    pds_url = pds_endpoint(did_doc)
    print(f"PDS: {pds_url}")
    assert is_safe_url(pds_url)
    with hardened_http.get_session() as sess:
        resp = sess.get(f"{pds_url}/.well-known/oauth-protected-resource")
    resp.raise_for_status()

    # IMPORTANT: Authorization Server URL is untrusted input, SSRF mitigations are needed
    authsrv_url = resp.json()["authorization_servers"][0]
    print(f"Auth Server: {authsrv_url}")
    assert is_safe_url(authsrv_url)
    try:
        authsrv_meta = fetch_authsrv_meta(authsrv_url)
    except Exception as err:
        print(f"failed to fetch authsrv_meta: " + str(err))
        flash("Failed to fetch Auth Server (Entryway) OAuth metadata")
        return render_template("login.html"), 400

    app_url = request.url_root.replace("http://", "https://")
    client_id = f"{app_url}oauth/client-metadata.json"

    pkce_verifier, state, nonce, resp = send_par_auth_request(
        authsrv_url, authsrv_meta, did, app_url, secret_jwk
    )
    resp.raise_for_status()
    request_uri = resp.json()["request_uri"]

    # create a DPoP keypair for this user session now (TODO: why now?)
    dpop_private_jwk = JsonWebKey.generate_key("EC", "P-256", is_private=True).as_json(
        is_private=True
    )

    # persist auth request to database
    print(f"saving oauth_auth_request to DB: {state}")
    query_db(
        "INSERT INTO oauth_auth_request (state, iss, nonce, pkce_verifier, dpop_private_jwk, did, handle, pds_url) VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        [
            state,
            authsrv_meta["issuer"],
            nonce,
            pkce_verifier,
            dpop_private_jwk,
            did,
            username,
            pds_url,
        ],
    )

    # IMPORTANT: Authorization endpoint URL is untrusted input, security mitigations are needed before redirecting user
    auth_url = authsrv_meta["authorization_endpoint"]
    assert is_safe_url(auth_url)
    qparam = urlencode({"client_id": client_id, "request_uri": request_uri})
    return redirect(f"{auth_url}?{qparam}")


@app.route("/oauth/authorize")
def oauth_authorize():
    # print(request.args)
    row = query_db(
        "SELECT * FROM oauth_auth_request WHERE state = ?;",
        [request.args["state"]],
        one=True,
    )
    if row is None:
        abort(400, "OAuth request not found")

    # delete row to prevent replay
    query_db("DELETE FROM oauth_auth_request WHERE state = ?;", [request.args["state"]])

    # verify query param "iss" against earlier oauth request "iss"
    assert row["iss"] == request.args["iss"]
    assert row["state"] == request.args["state"]

    app_url = request.url_root.replace("http://", "https://")
    tokens, dpop_nonce = complete_auth_request(
        row, request.args["code"], app_url, secret_jwk
    )

    # save session in database
    query_db(
        "INSERT OR REPLACE INTO oauth_session (did, handle, pds_url, iss, access_token, refresh_token, dpop_nonce, dpop_private_jwk) VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        [
            row["did"],
            row["handle"],
            row["pds_url"],
            row["iss"],
            tokens["access_token"],
            tokens["refresh_token"],
            dpop_nonce,
            row["dpop_private_jwk"],
        ],
    )
    # save user identifier in (secure) session cookie
    session["user_did"] = row["did"]

    return redirect("/bsky/post")


@login_required
@app.route("/oauth/logout")
def oauth_logout():
    query_db("DELETE FROM oauth_session WHERE did = ?;", [g.user["did"]])
    session.clear()
    return redirect("/")


@login_required
@app.route("/bsky/post", methods=("GET", "POST"))
def bsky_post():
    if request.method != "POST":
        return render_template("bsky_post.html")

    pds_url = g.user["pds_url"]
    req_url = f"{pds_url}/xrpc/com.atproto.repo.createRecord"

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "repo": g.user["did"],
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": request.form["post_text"],
            "createdAt": now,
        },
    }
    resp = pds_auth_req("POST", req_url, body=body, user=g.user, db=get_db())
    resp.raise_for_status()

    flash("Post record created in PDS!")
    return render_template("bsky_post.html")
