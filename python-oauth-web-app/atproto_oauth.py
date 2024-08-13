from urllib.parse import urlparse
import time
import json
from authlib.jose import JsonWebKey
from authlib.common.security import generate_token
from authlib.jose import jwt
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from atproto_security import is_safe_url, hardened_http


# Checks an Authorization Server metadata response against atproto OAuth requirements
def is_valid_authsrv_meta(obj, url):
    fetch_url = urlparse(url)
    issuer_url = urlparse(obj["issuer"])
    assert issuer_url.hostname == fetch_url.hostname
    assert issuer_url.scheme == "https"
    assert issuer_url.port == None
    assert issuer_url.path in ["", "/"]
    assert issuer_url.params == ""
    assert issuer_url.fragment == ""

    assert "code" in obj["response_types_supported"]
    assert "authorization_code" in obj["grant_types_supported"]
    assert "refresh_token" in obj["grant_types_supported"]
    assert "S256" in obj["code_challenge_methods_supported"]
    assert "none" in obj["token_endpoint_auth_methods_supported"]
    assert "private_key_jwt" in obj["token_endpoint_auth_methods_supported"]
    assert "ES256" in obj["token_endpoint_auth_signing_alg_values_supported"]
    # TODO: shoudl we be enforcing this?
    # assert "refresh_token" in obj["scopes_supported"]
    assert "profile" in obj["scopes_supported"]
    # NOTE: we don't really use email, it is just required for OIDC (?)
    assert "email" in obj["scopes_supported"]
    if "subject_types_supported" in obj:
        assert "public" in obj["subject_types_supported"]
    assert True == obj["authorization_response_iss_parameter_supported"]
    assert obj["pushed_authorization_request_endpoint"] is not None
    assert True == obj["require_pushed_authorization_requests"]
    assert "ES256" in obj["dpop_signing_alg_values_supported"]
    if "require_request_uri_registration" in obj:
        assert True == obj["require_request_uri_registration"]
    assert True == obj["client_id_metadata_document_supported"]

    return True


# Does an HTTP GET for Authorization Server (entryway) metadata, returning it as a dict
def fetch_authsrv_meta(url):
    print("Auth Server Metadata URL: " + url)
    # IMPORTANT: Authorization Server URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(url)
    with hardened_http.get_session() as sess:
        resp = sess.get(f"{url}/.well-known/oauth-authorization-server")
    resp.raise_for_status()

    authsrv_meta = resp.json()
    # print("Auth Server Metadata: " + json.dumps(authsrv_meta, indent=2))
    assert is_valid_authsrv_meta(authsrv_meta, url)
    return authsrv_meta


# Prepares and sends a pushed auth request (PAR) via HTTP POST to the Authorization Server.
# Returns "state" id, nonce, and HTTP response on success, without checking HTTP response status
def send_par_auth_request(authsrv_url, authsrv_meta, username, app_url, secret_jwk):
    par_url = authsrv_meta["pushed_authorization_request_endpoint"]
    issuer = authsrv_meta["issuer"]
    state = generate_token()
    nonce = generate_token()
    pkce_verifier = generate_token(48)
    redirect_uri = f"{app_url}oauth/callback"
    client_id = f"{app_url}oauth/client-metadata.json"
    # TODO: are these the best scopes to request for this demo?
    scope = "openid profile offline_access"

    # Generate PKCE code_challenge, and use it for PAR request
    code_challenge = create_s256_code_challenge(pkce_verifier)
    code_challenge_method = "S256"

    # Self-signed JWT using the private key declared in client metadata JWKS
    client_assertion = jwt.encode(
        {"alg": "ES256", "kid": secret_jwk["kid"]},
        {
            "iss": client_id,
            "sub": client_id,
            "aud": authsrv_url,
            "jti": generate_token(),
            "iat": int(time.time()),
        },
        secret_jwk,
    ).decode("utf-8")

    par_body = {
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "client_id": client_id,
        "state": state,
        "nonce": nonce,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "login_hint": username,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }
    # print(par_body)

    # TODO: could be doing DPoP here
    # IMPORTANT: Pushed Authorization Request URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(par_url)
    with hardened_http.get_session() as sess:
        resp = sess.post(
            par_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=par_body,
        )
    return pkce_verifier, state, nonce, resp


def complete_auth_request(auth_request, code, app_url, secret_jwk):

    state = auth_request["state"]
    authsrv_url = auth_request["iss"]

    # Re-fetch server metadata
    authsrv_meta = fetch_authsrv_meta(authsrv_url)

    # Construct auth token request fields
    client_id = f"{app_url}oauth/client-metadata.json"
    redirect_uri = f"{app_url}oauth/callback"

    # This is where the "confidential client" secret key is used
    client_assertion = jwt.encode(
        {"alg": "ES256", "kid": secret_jwk["kid"]},
        {
            "iss": client_id,
            "sub": client_id,
            "aud": authsrv_url,
            "jti": generate_token(),
            "iat": int(time.time()),
        },
        secret_jwk,
    ).decode("utf-8")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": auth_request["pkce_verifier"],
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }

    # Create DPoP header JWT, using the existing DPoP signing key for this account/session
    token_url = authsrv_meta["token_endpoint"]
    dpop_key = JsonWebKey.import_key(json.loads(auth_request["dpop_private_jwk"]))
    dpop_pub_jwk = json.loads(dpop_key.as_json(is_private=False))
    dpop_proof = jwt.encode(
        {"typ": "dpop+jwt", "alg": "ES256", "jwk": dpop_pub_jwk},
        {
            "jti": generate_token(),
            "htm": "POST",
            "htu": token_url,
            "iat": int(time.time()),
            "exp": int(time.time()) + 30,
        },
        dpop_key,
    ).decode("utf-8")

    # TODO: should we be reusing earlier DPoP nonce?
    dpop_nonce = ""
    # IMPORTANT: Token URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(token_url)
    with hardened_http.get_session() as sess:
        resp = sess.post(token_url, data=params, headers={"DPoP": dpop_proof})

    # Handle DPoP missing/invalid nonce error by retrying with server-provided nonce
    if resp.status_code == 400 and resp.json()["error"] == "use_dpop_nonce":
        server_nonce = resp.headers["DPoP-Nonce"]
        # print(server_nonce)
        dpop_proof = jwt.encode(
            {"typ": "dpop+jwt", "alg": "ES256", "jwk": dpop_pub_jwk},
            {
                "jti": generate_token(),
                "htm": "POST",
                "htu": token_url,
                "nonce": server_nonce,
                "iat": int(time.time()),
                "exp": int(time.time()) + 30,
            },
            dpop_key,
        ).decode("utf-8")
        with hardened_http.get_session() as sess:
            resp = sess.post(token_url, data=params, headers={"DPoP": dpop_proof})

    resp.raise_for_status()
    token_body = resp.json()

    # Validate against request DID (even if original "username" was a handle)
    assert token_body["sub"] == auth_request["did"]

    return token_body, dpop_nonce


# Helper to demonstrate making a request (HTTP GET or POST) to the user's PDS ("Resource Server" in OAuth terminology) using DPoP and access token.
# This method returns a 'requests' reponse, without checking status code.
def pds_auth_req(method, url, user, db, body=None):

    dpop_key = JsonWebKey.import_key(json.loads(user["dpop_private_jwk"]))
    dpop_pub_jwk = json.loads(dpop_key.as_json(is_private=False))
    dpop_nonce = user["dpop_nonce"]
    access_token = user["access_token"]

    # Might need to retry request with a new nonce.
    for i in range(2):
        # print(f"access with nonce: {dpop_nonce}")
        dpop_jwt = jwt.encode(
            {"typ": "dpop+jwt", "alg": "ES256", "jwk": dpop_pub_jwk},
            {
                "iss": user["iss"],
                "iat": int(time.time()),
                "exp": int(time.time()) + 10,
                "jti": generate_token(),
                "htm": "POST",
                "htu": url,
                "nonce": dpop_nonce,
                # PKCE S256 is same as DPoP ath hashing
                "ath": create_s256_code_challenge(access_token),
            },
            dpop_key,
        ).decode("utf-8")

        with hardened_http.get_session() as sess:
            resp = sess.post(
                url,
                headers={"Authorization": f"DPoP {access_token}", "DPoP": dpop_jwt},
                json=body,
            )

        # If we got a new server-provided DPoP nonce, store it in database and retry.
        if resp.status_code in [400, 401] and resp.json()["error"] == "use_dpop_nonce":
            # print(resp.headers)
            dpop_nonce = resp.headers["DPoP-Nonce"]
            # update session database with new nonce
            cur = db.cursor()
            cur.execute(
                "UPDATE oauth_session SET dpop_nonce = ? WHERE did = ?;",
                [dpop_nonce, user["did"]],
            )
            db.commit()
            cur.close()
            continue
        break

    return resp
