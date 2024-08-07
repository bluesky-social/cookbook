from urllib.parse import urlparse
import requests


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
    resp = requests.get(f"{url}/.well-known/oauth-authorization-server")
    resp.raise_for_status()

    authsrv_meta = resp.json()
    # print("Auth Server Metadata: " + json.dumps(authsrv_meta, indent=2))
    assert valid_authsrv_meta(authsrv_meta, url)
    return authsrv_meta


# TODO: not actually using this, because it doesn't support DPoP yet
def oauth_client(request, authsrv_meta):
    sess = OAuth2Session(
        client_id=client_id,
        authorization_endpoint=authsrv_meta["authorization_endpoint"],
        token_endpoint=authsrv_meta["token_endpoint"],
        token_endpoint_auth_method="private_key_jwt",
        revocation_endpoint=authsrv_meta["revocation_endpoint"],
        revocation_endpoint_auth_method="private_key_jwt",
        redirect_uri=redirect_uri,
        code_challenge_method="S256",
    )
    return sess
