from urllib.parse import urlparse
from typing import Any, Tuple
import time
import json
from authlib.jose import JsonWebKey
from authlib.common.security import generate_token
from authlib.jose import jwt
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from atproto_security import is_safe_url, hardened_http


# Checks an Authorization Server metadata response against atproto OAuth requirements
def is_valid_authserver_meta(obj: dict, url: str) -> bool:
    fetch_url = urlparse(url)
    issuer_url = urlparse(obj["issuer"])
    assert issuer_url.hostname == fetch_url.hostname
    assert issuer_url.scheme == "https"
    assert issuer_url.port is None
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
    assert "atproto" in obj["scopes_supported"]
    assert obj["authorization_response_iss_parameter_supported"] is True
    assert obj["pushed_authorization_request_endpoint"] is not None
    assert obj["require_pushed_authorization_requests"] is True
    assert "ES256" in obj["dpop_signing_alg_values_supported"]
    if "require_request_uri_registration" in obj:
        assert obj["require_request_uri_registration"] is True
    assert obj["client_id_metadata_document_supported"] is True

    return True


# Takes a Resource Server (PDS) URL, and tries to resolve it to an Authorization Server host/origin
def resolve_pds_authserver(url: str) -> str:
    # IMPORTANT: PDS endpoint URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(url)
    with hardened_http.get_session() as sess:
        resp = sess.get(f"{url}/.well-known/oauth-protected-resource")
    resp.raise_for_status()
    # Additionally check that status is exactly 200 (not just 2xx)
    assert resp.status_code == 200
    authserver_url = resp.json()["authorization_servers"][0]
    return authserver_url


# Does an HTTP GET for Authorization Server (entryway) metadata, verify the contents, and return the metadata as a dict
def fetch_authserver_meta(url: str) -> dict:
    # IMPORTANT: Authorization Server URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(url)
    with hardened_http.get_session() as sess:
        resp = sess.get(f"{url}/.well-known/oauth-authorization-server")
    resp.raise_for_status()

    authserver_meta = resp.json()
    # print("Auth Server Metadata: " + json.dumps(authserver_meta, indent=2))
    assert is_valid_authserver_meta(authserver_meta, url)
    return authserver_meta


def client_assertion_jwt(
    client_id: str, authserver_url: str, client_secret_jwk: JsonWebKey
) -> str:
    client_assertion = jwt.encode(
        {"alg": "ES256", "kid": client_secret_jwk["kid"]},
        {
            "iss": client_id,
            "sub": client_id,
            "aud": authserver_url,
            "jti": generate_token(),
            "iat": int(time.time()),
        },
        client_secret_jwk,
    ).decode("utf-8")
    return client_assertion


def authserver_dpop_jwt(
    method: str, url: str, nonce: str, dpop_private_jwk: JsonWebKey
) -> str:
    dpop_pub_jwk = json.loads(dpop_private_jwk.as_json(is_private=False))
    body = {
        "jti": generate_token(),
        "htm": method,
        "htu": url,
        "iat": int(time.time()),
        "exp": int(time.time()) + 30,
    }
    if nonce:
        body["nonce"] = nonce
    dpop_proof = jwt.encode(
        {"typ": "dpop+jwt", "alg": "ES256", "jwk": dpop_pub_jwk},
        body,
        dpop_private_jwk,
    ).decode("utf-8")
    return dpop_proof


# Prepares and sends a pushed auth request (PAR) via HTTP POST to the Authorization Server.
# Returns "state" id HTTP response on success, without checking HTTP response status
def send_par_auth_request(
    authserver_url: str,
    authserver_meta: dict,
    login_hint: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    client_secret_jwk: JsonWebKey,
    dpop_private_jwk: JsonWebKey,
) -> Tuple[str, str, str, Any]:
    par_url = authserver_meta["pushed_authorization_request_endpoint"]
    state = generate_token()
    pkce_verifier = generate_token(48)

    # Generate PKCE code_challenge, and use it for PAR request
    code_challenge = create_s256_code_challenge(pkce_verifier)
    code_challenge_method = "S256"

    # Self-signed JWT using the private key declared in client metadata JWKS (confidential client)
    client_assertion = client_assertion_jwt(
        client_id, authserver_url, client_secret_jwk
    )

    # Create DPoP header JWT; we don't have a server Nonce yet
    dpop_authserver_nonce = ""
    dpop_proof = authserver_dpop_jwt(
        "POST", par_url, dpop_authserver_nonce, dpop_private_jwk
    )

    par_body = {
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "client_id": client_id,
        "state": state,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }
    if login_hint:
        par_body["login_hint"] = login_hint
    # print(par_body)

    # IMPORTANT: Pushed Authorization Request URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(par_url)
    with hardened_http.get_session() as sess:
        resp = sess.post(
            par_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "DPoP": dpop_proof,
            },
            data=par_body,
        )

    # Handle DPoP missing/invalid nonce error by retrying with server-provided nonce
    if resp.status_code == 400 and resp.json()["error"] == "use_dpop_nonce":
        dpop_authserver_nonce = resp.headers["DPoP-Nonce"]
        print(f"retrying with new auth server DPoP nonce: {dpop_authserver_nonce}")
        dpop_proof = authserver_dpop_jwt(
            "POST", par_url, dpop_authserver_nonce, dpop_private_jwk
        )
        with hardened_http.get_session() as sess:
            resp = sess.post(
                par_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "DPoP": dpop_proof,
                },
                data=par_body,
            )

    return pkce_verifier, state, dpop_authserver_nonce, resp


# Completes the auth flow by sending an initial auth token request.
# Returns token response (dict) and DPoP nonce (str)
def initial_token_request(
    auth_request: dict,
    code: str,
    app_url: str,
    client_secret_jwk: JsonWebKey,
) -> Tuple[dict, str]:
    authserver_url = auth_request["authserver_iss"]

    # Re-fetch server metadata
    authserver_meta = fetch_authserver_meta(authserver_url)

    # Construct auth token request fields
    client_id = f"{app_url}oauth/client-metadata.json"
    redirect_uri = f"{app_url}oauth/callback"

    # Self-signed JWT using the private key declared in client metadata JWKS (confidential client)
    client_assertion = client_assertion_jwt(
        client_id, authserver_url, client_secret_jwk
    )

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
    token_url = authserver_meta["token_endpoint"]
    dpop_private_jwk = JsonWebKey.import_key(
        json.loads(auth_request["dpop_private_jwk"])
    )
    dpop_authserver_nonce = auth_request["dpop_authserver_nonce"]
    dpop_proof = authserver_dpop_jwt(
        "POST", token_url, dpop_authserver_nonce, dpop_private_jwk
    )

    # IMPORTANT: Token URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(token_url)
    with hardened_http.get_session() as sess:
        resp = sess.post(token_url, data=params, headers={"DPoP": dpop_proof})

    # Handle DPoP missing/invalid nonce error by retrying with server-provided nonce
    if resp.status_code == 400 and resp.json()["error"] == "use_dpop_nonce":
        dpop_authserver_nonce = resp.headers["DPoP-Nonce"]
        print(f"retrying with new auth server DPoP nonce: {dpop_authserver_nonce}")
        # print(server_nonce)
        dpop_proof = authserver_dpop_jwt(
            "POST", token_url, dpop_authserver_nonce, dpop_private_jwk
        )
        with hardened_http.get_session() as sess:
            resp = sess.post(token_url, data=params, headers={"DPoP": dpop_proof})

    resp.raise_for_status()
    token_body = resp.json()

    # IMPORTANT: the 'sub' field must be verified against the original request by code calling this function.

    return token_body, dpop_authserver_nonce


# Returns token response (dict) and DPoP nonce (str)
def refresh_token_request(
    user: dict,
    app_url: str,
    client_secret_jwk: JsonWebKey,
) -> Tuple[dict, str]:
    authserver_url = user["authserver_iss"]

    # Re-fetch server metadata
    authserver_meta = fetch_authserver_meta(authserver_url)

    # Construct token request fields
    client_id = f"{app_url}oauth/client-metadata.json"

    # Self-signed JWT using the private key declared in client metadata JWKS (confidential client)
    client_assertion = client_assertion_jwt(
        client_id, authserver_url, client_secret_jwk
    )

    params = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": user["refresh_token"],
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }

    # Create DPoP header JWT, using the existing DPoP signing key for this account/session
    token_url = authserver_meta["token_endpoint"]
    dpop_private_jwk = JsonWebKey.import_key(json.loads(user["dpop_private_jwk"]))
    dpop_authserver_nonce = user["dpop_authserver_nonce"]
    dpop_proof = authserver_dpop_jwt(
        "POST", token_url, dpop_authserver_nonce, dpop_private_jwk
    )

    # IMPORTANT: Token URL is untrusted input, SSRF mitigations are needed
    assert is_safe_url(token_url)
    with hardened_http.get_session() as sess:
        resp = sess.post(token_url, data=params, headers={"DPoP": dpop_proof})

    # Handle DPoP missing/invalid nonce error by retrying with server-provided nonce
    if resp.status_code == 400 and resp.json()["error"] == "use_dpop_nonce":
        dpop_authserver_nonce = resp.headers["DPoP-Nonce"]
        print(f"retrying with new auth server DPoP nonce: {dpop_authserver_nonce}")
        # print(server_nonce)
        dpop_proof = authserver_dpop_jwt(
            "POST", token_url, dpop_authserver_nonce, dpop_private_jwk
        )
        with hardened_http.get_session() as sess:
            resp = sess.post(token_url, data=params, headers={"DPoP": dpop_proof})

    if resp.status_code not in [200, 201]:
        print(f"Token Refresh Error: {resp.json()}")

    resp.raise_for_status()
    token_body = resp.json()

    return token_body, dpop_authserver_nonce


def pds_dpop_jwt(
    method: str,
    url: str,
    iss: str,
    access_token: str,
    nonce: str,
    dpop_private_jwk: JsonWebKey,
) -> str:
    dpop_pub_jwk = json.loads(dpop_private_jwk.as_json(is_private=False))
    body = {
        "iss": iss,
        "iat": int(time.time()),
        "exp": int(time.time()) + 10,
        "jti": generate_token(),
        "htm": method,
        "htu": url,
        # PKCE S256 is same as DPoP ath hashing
        "ath": create_s256_code_challenge(access_token),
    }
    if nonce:
        body["nonce"] = nonce
    dpop_proof = jwt.encode(
        {"typ": "dpop+jwt", "alg": "ES256", "jwk": dpop_pub_jwk},
        body,
        dpop_private_jwk,
    ).decode("utf-8")
    return dpop_proof


# Helper to demonstrate making a request (HTTP GET or POST) to the user's PDS ("Resource Server" in OAuth terminology) using DPoP and access token.
# This method returns a 'requests' reponse, without checking status code.
def pds_authed_req(method: str, url: str, user: dict, db: Any, body=None) -> Any:
    dpop_private_jwk = JsonWebKey.import_key(json.loads(user["dpop_private_jwk"]))
    dpop_pds_nonce = user["dpop_pds_nonce"]
    access_token = user["access_token"]

    # Might need to retry request with a new nonce.
    for i in range(2):
        dpop_jwt = pds_dpop_jwt(
            "POST",
            url,
            user["authserver_iss"],
            access_token,
            dpop_pds_nonce,
            dpop_private_jwk,
        )

        with hardened_http.get_session() as sess:
            resp = sess.post(
                url,
                headers={
                    "Authorization": f"DPoP {access_token}",
                    "DPoP": dpop_jwt,
                },
                json=body,
            )

        # If we got a new server-provided DPoP nonce, store it in database and retry.
        # NOTE: the type of error might also be communicated in the `WWW-Authenticate` HTTP response header.
        if resp.status_code in [400, 401] and resp.json()["error"] == "use_dpop_nonce":
            # print(resp.headers)
            dpop_pds_nonce = resp.headers["DPoP-Nonce"]
            print(f"retrying with new PDS DPoP nonce: {dpop_pds_nonce}")
            # update session database with new nonce
            cur = db.cursor()
            cur.execute(
                "UPDATE oauth_session SET dpop_pds_nonce = ? WHERE did = ?;",
                [dpop_pds_nonce, user["did"]],
            )
            db.commit()
            cur.close()
            continue
        break

    return resp
