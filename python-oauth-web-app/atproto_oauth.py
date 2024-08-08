from urllib.parse import urlparse
import requests
import time
import json
from authlib.jose import JsonWebKey
from authlib.common.security import generate_token
from authlib.jose import jwt
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from security import is_safe_url


def valid_authsrv_meta(obj, url):
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
    # assert "refresh_token" in obj["scopes_supported"]
    assert "profile" in obj["scopes_supported"]
    assert "email" in obj["scopes_supported"]  # TODO
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


def fetch_authsrv_meta(url):
    # TODO: ensure URL is safe
    # fetch auth server metadata
    assert is_safe_url(url)
    resp = requests.get(f"{url}/.well-known/oauth-authorization-server")
    resp.raise_for_status()

    authsrv_meta = resp.json()
    # print("Auth Server Metadata: " + json.dumps(authsrv_meta, indent=2))
    assert valid_authsrv_meta(authsrv_meta, url)
    return authsrv_meta


# prepares and sends a pushed auth request (PAR) via HTTP POST to the Authorization Server.
# returns "state" id, nonce, and HTTP response on success, without checking HTTP response status
def send_par_auth_request(authsrv_url, authsrv_meta, account_did, app_url, secret_jwk):
    par_url = authsrv_meta["pushed_authorization_request_endpoint"]
    issuer = authsrv_meta["issuer"]
    state = generate_token()
    nonce = generate_token()
    pkce_verifier = generate_token(48)
    redirect_uri = f"{app_url}oauth/authorize"
    client_id = f"{app_url}oauth/client-metadata.json"
    scope = "openid profile offline_access"

    # generate PKCE code_challenge, and use it for PAR request
    code_challenge = create_s256_code_challenge(pkce_verifier)
    code_challenge_method = "S256"

    # self-signed JWT using the private key declared in client metadata JWKS
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
        "login_hint": account_did,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion,
    }
    # print(par_body)
    # TODO: check that URL is safe
    assert is_safe_url(par_url)
    resp = requests.post(
        par_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=par_body,
    )
    # print(resp.json())
    return pkce_verifier, state, nonce, resp


def complete_auth_request(auth_request, code, app_url, secret_jwk):

    state = auth_request["state"]
    authsrv_url = auth_request["iss"]

    dpop_key = JsonWebKey.import_key(json.loads(auth_request["dpop_private_jwk"]))
    dpop_pub_jwk = json.loads(dpop_key.as_json(is_private=False))

    # fetch server metadata again
    authsrv_meta = fetch_authsrv_meta(authsrv_url)

    # construct auth request
    client_id = f"{app_url}oauth/client-metadata.json"
    redirect_uri = f"{app_url}oauth/authorize"
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

    # create DPoP header JWT
    token_url = authsrv_meta["token_endpoint"]
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

    print(params)
    # TODO: check if safe URL
    assert is_safe_url(token_url)
    dpop_nonce = ""
    resp = requests.post(token_url, data=params, headers={"DPoP": dpop_proof})
    if resp.status_code == 400 and resp.json()["error"] == "use_dpop_nonce":
        # print(resp.headers)
        server_nonce = resp.headers["DPoP-Nonce"]  # Dpop-Nonce
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
        resp = requests.post(token_url, data=params, headers={"DPoP": dpop_proof})

    # print(resp.json())
    resp.raise_for_status()
    token_body = resp.json()

    # validate against request DID
    assert token_body["sub"] == auth_request["did"]

    return token_body, dpop_nonce


def pds_auth_req(method, url, user, db, body=None):

    dpop_key = JsonWebKey.import_key(json.loads(user["dpop_private_jwk"]))
    dpop_pub_jwk = json.loads(dpop_key.as_json(is_private=False))
    dpop_nonce = user["dpop_nonce"]
    access_token = user["access_token"]

    for i in range(2):
        #print(f"access with nonce: {dpop_nonce}")
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

        resp = requests.post(
            url,
            headers={"Authorization": f"DPoP {access_token}", "DPoP": dpop_jwt},
            json=body,
        )
        if resp.status_code in [400, 401] and resp.json()["error"] == "use_dpop_nonce":
            # print(resp.headers)
            dpop_nonce = resp.headers["DPoP-Nonce"]
            # update session database with new nonce
            cur = db.cursor()
            cur.execute(
                "UPDATE oauth_session SET dpop_nonce = ? WHERE did = ?;", [dpop_nonce, user["did"]]
            )
            db.commit()
            cur.close()
            continue
        break
    # print(resp.json())
    return resp
