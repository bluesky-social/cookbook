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

# Load this configuration from environment variables (which might mean a .env "dotenv" file)
app.config.from_prefixed_env()

# This is a "confidential" OAuth client, meaning it has access to a persistent secret signing key. parse that key as a global.
secret_jwk = JsonWebKey.import_key(app.config["SECRET_JWK"])
pub_jwk = json.loads(secret_jwk.as_json(is_private=False))
# Defensively check that the public JWK is really public and didn't somehow end up with secret cryptographic key info
assert "d" not in pub_jwk


# Helpers for managing database connection
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db_path = app.config.get("DATABASE_URL", "demo.sqlite")
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


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


# Load back-end account auth metadata when there is a valid front-end session cookie
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


# Actual web routes start here!
@app.route("/")
def homepage():
    return render_template("home.html")


# Every atproto OAuth client must have a public client metadata JSON document. It doesn't need to be at this specific path. The full URL to this file is the "client_id" of the app.
# This implementation dynamically uses the HTTP request Host name to infer the "client_id".
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
            "redirect_uris": [f"{app_url}oauth/callback"],
            "client_uri": app_url,
            "subject_type": "public",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],  # TODO: "code id_token"?
            "scope": "openid profile offline_access",
            "client_name": "atproto OAuth Flask Backend Demo",
            "token_endpoint_auth_method": "none",
            # NOTE: in theory we can return the public key (in JWK format) inline
            # "jwks": { #    "keys": [pub_jwk], #},
            "jwks_uri": f"{app_url}oauth/jwks.json",
        }
    )


# In this example of a "confidential" OAuth client, we have only a single app key being used. In a production-grade client, it best practice to periodically rotate keys. Including both a "new key" and "old key" at the same time can make this process smoother.
@app.route("/oauth/jwks.json")
def oauth_jwks():
    return jsonify(
        {
            "keys": [pub_jwk],
        }
    )


# Displays the login form (GET), or starts the OAuth authorization flow (POST).
@app.route("/oauth/login", methods=("GET", "POST"))
def oauth_login():
    if request.method != "POST":
        return render_template("login.html")

    # Resolve handle and/or DID document, using atproto identity helpers.
    # The supplied username could be either a handle or a DID (this example
    # does not support supplying a PDS endpoint). We are calling whatever the
    # user supplied the "username".
    # A production-grade client might want to resolve the handle here even if a
    # DID was supplied for login.
    username = request.form["username"]
    if not username.startswith("did:"):
        if not valid_handle(username):
            flash("Invalid Handle")
            return render_template("login.html"), 400
        did = resolve_handle(username)
        if not did:
            flash("Handle Not Found")
            return render_template("login.html"), 400
    else:
        did = username
    if not valid_did(did):
        flash("Invalid DID: " + did)
        return render_template("login.html"), 400
    did_doc = resolve_did(did)
    if not did_doc:
        flash("DID Not Found: " + did)
        return render_template("login.html"), 400

    # Fetch PDS OAuth metadata.
    # IMPORTANT: PDS endpoint URL is untrusted input, SSRF mitigations are needed
    pds_url = pds_endpoint(did_doc)
    print(f"account PDS: {pds_url}")
    assert is_safe_url(pds_url)
    with hardened_http.get_session() as sess:
        resp = sess.get(f"{pds_url}/.well-known/oauth-protected-resource")
    resp.raise_for_status()
    # Additionally check that status is exactly 200 (not just 2xx)
    assert resp.status_code == 200

    # Fetch Auth Server metadata. For a self-hosted PDS, this will be the same server (the PDS). For large-scale PDS hosts like Bluesky, this may be a separate "entryway" server filling the Auth Server role.
    # IMPORTANT: Authorization Server URL is untrusted input, SSRF mitigations are needed
    authsrv_url = resp.json()["authorization_servers"][0]
    print(f"account Auth Server: {authsrv_url}")
    assert is_safe_url(authsrv_url)
    try:
        authsrv_meta = fetch_authsrv_meta(authsrv_url)
    except Exception as err:
        print(f"failed to fetch auth server metadata: " + str(err))
        flash("Failed to fetch Auth Server (Entryway) OAuth metadata")
        return render_template("login.html"), 400

    # Dynamically compute our "client_id" based on the request HTTP Host
    app_url = request.url_root.replace("http://", "https://")
    client_id = f"{app_url}oauth/client-metadata.json"

    # Generate DPoP private signing key for this account session. In theory this could be defered until the token request at the end of the athentication flow, but doing it now allows early binding during the PAR request.
    # TODO: nonce?
    dpop_private_jwk = JsonWebKey.generate_key("EC", "P-256", is_private=True).as_json(
        is_private=True
    )

    # Submit OAuth Pushed Authentication Request (PAR). We could have constructed a more complex authentication request URL below instead, but there are some advantages with PAR, including failing fast, early DPoP binding, and no URL length limitations.
    # TODO: use dpop_private_jwk here, along with a nonce?
    pkce_verifier, state, nonce, resp = send_par_auth_request(
        authsrv_url, authsrv_meta, did, app_url, secret_jwk
    )
    resp.raise_for_status()
    # This field is confusingly named: it is basically a token to refering back to the successful PAR request.
    par_request_uri = resp.json()["request_uri"]

    print(f"saving oauth_auth_request to DB: {state}")
    query_db(
        "INSERT INTO oauth_auth_request (state, iss, nonce, pkce_verifier, dpop_private_jwk, did, username, pds_url) VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
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

    # Forward the user to the Authorization Server to complete the browser auth flow.
    # IMPORTANT: Authorization endpoint URL is untrusted input, security mitigations are needed before redirecting user
    auth_url = authsrv_meta["authorization_endpoint"]
    assert is_safe_url(auth_url)
    qparam = urlencode({"client_id": client_id, "request_uri": par_request_uri})
    return redirect(f"{auth_url}?{qparam}")


# Endpoint for receiving "callback" responses from the Authorization Server, to complete the auth flow.
@app.route("/oauth/callback")
def oauth_callback():
    state = request.args["state"]
    iss = request.args["iss"]
    code = request.args["code"]

    # Lookup auth request by the "state" token (which we randomly generated earlier)
    row = query_db(
        "SELECT * FROM oauth_auth_request WHERE state = ?;",
        [state],
        one=True,
    )
    if row is None:
        abort(400, "OAuth request not found")

    # Delete row to prevent response replay
    query_db("DELETE FROM oauth_auth_request WHERE state = ?;", [state])

    # Verify query param "iss" against earlier oauth request "iss"
    assert row["iss"] == iss
    # This is redundant with the above SQL query, but also double-checking that the "state" param matches the original request
    assert row["state"] == state

    # Complete the auth flow by requesting auth tokens from the authorization server.
    app_url = request.url_root.replace("http://", "https://")
    tokens, dpop_nonce = complete_auth_request(row, code, app_url, secret_jwk)

    # Save session (including auth tokens) in database
    query_db(
        "INSERT OR REPLACE INTO oauth_session (did, username, pds_url, iss, access_token, refresh_token, dpop_nonce, dpop_private_jwk) VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        [
            row["did"],
            row["username"],
            row["pds_url"],
            row["iss"],
            tokens["access_token"],
            tokens["refresh_token"],
            dpop_nonce,
            row["dpop_private_jwk"],
        ],
    )

    # Set a (secure) session cookie in the user's browser, for authentication between the browser and this app
    session["user_did"] = row["did"]

    return redirect("/bsky/post")


@login_required
@app.route("/oauth/logout")
def oauth_logout():
    query_db("DELETE FROM oauth_session WHERE did = ?;", [g.user["did"]])
    session.clear()
    return redirect("/")


# Example form endpoint demonstrating making an authenticated request to the logged-in user's PDS to create a repository record.
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


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", status_code=500, err=e), 500


@app.errorhandler(400)
def bad_request_error(e):
    return render_template("error.html", status_code=400, err=e), 400
