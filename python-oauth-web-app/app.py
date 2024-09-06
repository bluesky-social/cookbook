import json
import sqlite3
import functools
from datetime import datetime, timezone
from urllib.parse import urlencode
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    jsonify,
    request,
    g,
    session,
    abort,
)
from authlib.jose import JsonWebKey

from atproto_identity import (
    is_valid_did,
    is_valid_handle,
    resolve_identity,
    pds_endpoint,
)
from atproto_oauth import (
    refresh_token_request,
    pds_authed_req,
    resolve_pds_authserver,
    initial_token_request,
    send_par_auth_request,
    fetch_authserver_meta,
)
from atproto_security import is_safe_url

app = Flask(__name__)

# Load this configuration from environment variables (which might mean a .env "dotenv" file)
app.config.from_prefixed_env()

# This is a "confidential" OAuth client, meaning it has access to a persistent secret signing key. parse that key as a global.
CLIENT_SECRET_JWK = JsonWebKey.import_key(app.config["CLIENT_SECRET_JWK"])
CLIENT_PUB_JWK = json.loads(CLIENT_SECRET_JWK.as_json(is_private=False))
# Defensively check that the public JWK is really public and didn't somehow end up with secret cryptographic key info
assert "d" not in CLIENT_PUB_JWK


# Helpers for managing database connection.
# Note that you could use a sqlite ":memory:" database instead. In that case you would want to have a global sqlite connection, instead of re-connecting per connection. This file-based setup is following the Flask docs/tutorial.
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
# NOTE: Flask uses encrypted cookies for sessions. If the SECRET_KEY config variable isn't provided, Flask will error out when trying to use the session.
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


# Every atproto OAuth client must have a public client metadata JSON document. It does not need to be at this specific path. The full URL to this file is the "client_id" of the app.
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
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": "atproto transition:generic",
            "token_endpoint_auth_method": "private_key_jwt",
            "token_endpoint_auth_signing_alg": "ES256",
            # NOTE: in theory we can return the public key (in JWK format) inline
            # "jwks": { #    "keys": [CLIENT_PUB_JWK], #},
            "jwks_uri": f"{app_url}oauth/jwks.json",
            # the following are optional fields, which might not be displayed by auth server
            "client_name": "atproto OAuth Flask Backend Demo",
            "client_uri": app_url,
        }
    )


# In this example of a "confidential" OAuth client, we have only a single app key being used. In a production-grade client, it best practice to periodically rotate keys. Including both a "new key" and "old key" at the same time can make this process smoother.
@app.route("/oauth/jwks.json")
def oauth_jwks():
    return jsonify(
        {
            "keys": [CLIENT_PUB_JWK],
        }
    )


# Displays the login form (GET), or starts the OAuth authorization flow (POST).
@app.route("/oauth/login", methods=("GET", "POST"))
def oauth_login():
    if request.method != "POST":
        return render_template("login.html")

    # Login can start with a handle, DID, or auth server URL. We are calling whatever the user supplied the "username".
    username = request.form["username"]
    if is_valid_handle(username) or is_valid_did(username):
        # If starting with an account identifier, resolve the identity (bi-directionally), fetch the PDS URL, and resolve to the Authorization Server URL
        login_hint = username
        did, handle, did_doc = resolve_identity(username)
        pds_url = pds_endpoint(did_doc)
        print(f"account PDS: {pds_url}")
        authserver_url = resolve_pds_authserver(pds_url)
    elif username.startswith("https://") and is_safe_url(username):
        # When starting with an auth server, we don't know about the account yet.
        did, handle, pds_url = None, None, None
        login_hint = None
        # Check if this is a Resource Server (PDS) URL; otherwise assume it is authorization server
        initial_url = username
        try:
            authserver_url = resolve_pds_authserver(initial_url)
        except Exception:
            authserver_url = initial_url
    else:
        flash("Not a valid handle, DID, or auth server URL")
        return render_template("login.html"), 400

    # Fetch Auth Server metadata. For a self-hosted PDS, this will be the same server (the PDS). For large-scale PDS hosts like Bluesky, this may be a separate "entryway" server filling the Auth Server role.
    # IMPORTANT: Authorization Server URL is untrusted input, SSRF mitigations are needed
    print(f"account Authorization Server: {authserver_url}")
    assert is_safe_url(authserver_url)
    try:
        authserver_meta = fetch_authserver_meta(authserver_url)
    except Exception as err:
        print(f"failed to fetch auth server metadata: {err}")
        # raise err
        flash("Failed to fetch Auth Server (Entryway) OAuth metadata")
        return render_template("login.html"), 400

    # Generate DPoP private signing key for this account session. In theory this could be defered until the token request at the end of the athentication flow, but doing it now allows early binding during the PAR request.
    dpop_private_jwk = JsonWebKey.generate_key("EC", "P-256", is_private=True)

    # OAuth scopes requested by this app
    scope = "atproto transition:generic"

    # Dynamically compute our "client_id" based on the request HTTP Host
    app_url = request.url_root.replace("http://", "https://")
    redirect_uri = f"{app_url}oauth/callback"
    client_id = f"{app_url}oauth/client-metadata.json"

    # Submit OAuth Pushed Authentication Request (PAR). We could have constructed a more complex authentication request URL below instead, but there are some advantages with PAR, including failing fast, early DPoP binding, and no URL length limitations.
    pkce_verifier, state, dpop_authserver_nonce, resp = send_par_auth_request(
        authserver_url,
        authserver_meta,
        login_hint,
        client_id,
        redirect_uri,
        scope,
        CLIENT_SECRET_JWK,
        dpop_private_jwk,
    )
    if resp.status_code == 400:
        print(f"PAR HTTP 400: {resp.json()}")
    resp.raise_for_status()
    # This field is confusingly named: it is basically a token to refering back to the successful PAR request.
    par_request_uri = resp.json()["request_uri"]

    print(f"saving oauth_auth_request to DB  state={state}")
    query_db(
        "INSERT INTO oauth_auth_request (state, authserver_iss, did, handle, pds_url, pkce_verifier, scope, dpop_authserver_nonce, dpop_private_jwk) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            state,
            authserver_meta["issuer"],
            did,  # might be None
            handle,  # might be None
            pds_url,  # might be None
            pkce_verifier,
            scope,
            dpop_authserver_nonce,
            dpop_private_jwk.as_json(is_private=True),
        ],
    )

    # Forward the user to the Authorization Server to complete the browser auth flow.
    # IMPORTANT: Authorization endpoint URL is untrusted input, security mitigations are needed before redirecting user
    auth_url = authserver_meta["authorization_endpoint"]
    assert is_safe_url(auth_url)
    qparam = urlencode({"client_id": client_id, "request_uri": par_request_uri})
    return redirect(f"{auth_url}?{qparam}")


# Endpoint for receiving "callback" responses from the Authorization Server, to complete the auth flow.
@app.route("/oauth/callback")
def oauth_callback():
    state = request.args["state"]
    authserver_iss = request.args["iss"]
    authorization_code = request.args["code"]

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
    assert row["authserver_iss"] == authserver_iss
    # This is redundant with the above SQL query, but also double-checking that the "state" param matches the original request
    assert row["state"] == state

    # Complete the auth flow by requesting auth tokens from the authorization server.
    app_url = request.url_root.replace("http://", "https://")
    tokens, dpop_authserver_nonce = initial_token_request(
        row,
        authorization_code,
        app_url,
        CLIENT_SECRET_JWK,
    )

    # Now we verify the account authentication against the original request
    if row["did"]:
        # If we started with an account identifier, this is simple
        did, handle, pds_url = row["did"], row["handle"], row["pds_url"]
        assert tokens["sub"] == did
    else:
        # If we started with an auth server URL, now we need to resolve the identity
        did = tokens["sub"]
        assert is_valid_did(did)
        did, handle, did_doc = resolve_identity(did)
        pds_url = pds_endpoint(did_doc)
        authserver_url = resolve_pds_authserver(pds_url)

        # Verify that Authorization Server matches
        assert authserver_url == authserver_iss

    # Verify that returned scope matches request (waiting for PDS update)
    assert row["scope"] == tokens["scope"]

    # Save session (including auth tokens) in database
    print(f"saving oauth_session to DB  {did}")
    query_db(
        "INSERT OR REPLACE INTO oauth_session (did, handle, pds_url, authserver_iss, access_token, refresh_token, dpop_authserver_nonce, dpop_private_jwk) VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        [
            did,
            handle,
            pds_url,
            authserver_iss,
            tokens["access_token"],
            tokens["refresh_token"],
            dpop_authserver_nonce,
            row["dpop_private_jwk"],
        ],
    )

    # Set a (secure) session cookie in the user's browser, for authentication between the browser and this app
    session["user_did"] = did
    # Note that the handle might change over time, and should be re-resolved periodically in a real app
    session["user_handle"] = handle

    return redirect("/bsky/post")


# Example endpoint demonstrating manual refreshing of auth token.
# This isn't something you would do in a real application, it is just to trigger this codepath.
@login_required
@app.route("/oauth/refresh")
def oauth_refresh():
    app_url = request.url_root.replace("http://", "https://")

    tokens, dpop_authserver_nonce = refresh_token_request(
        g.user, app_url, CLIENT_SECRET_JWK
    )

    # persist updated tokens (and DPoP nonce) to database
    query_db(
        "UPDATE oauth_session SET access_token = ?, refresh_token = ?, dpop_authserver_nonce = ? WHERE did = ?;",
        [
            tokens["access_token"],
            tokens["refresh_token"],
            dpop_authserver_nonce,
            g.user["did"],
        ],
    )

    flash("Token refreshed!")
    return redirect("/")


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
    resp = pds_authed_req("POST", req_url, body=body, user=g.user, db=get_db())
    if resp.status_code not in [200, 201]:
        print(f"PDS HTTP Error: {resp.json()}")
    resp.raise_for_status()

    flash("Post record created in PDS!")
    return render_template("bsky_post.html")


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", status_code=500, err=e), 500


@app.errorhandler(400)
def bad_request_error(e):
    return render_template("error.html", status_code=400, err=e), 400
