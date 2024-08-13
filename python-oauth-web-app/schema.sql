
CREATE TABLE IF NOT EXISTS oauth_auth_request (
    state TEXT,
    iss TEXT,
    did TEXT,
    username TEXT,
    pds_url TEXT,
    nonce TEXT,
    pkce_verifier TEXT,
    dpop_private_jwk TEXT,
    UNIQUE(state)
);

CREATE TABLE IF NOT EXISTS oauth_session (
    did TEXT,
    username TEXT,
    pds_url TEXT,
    iss TEXT,
    access_token TEXT,
    refresh_token TEXT,
    dpop_nonce TEXT,
    dpop_private_jwk TEXT,
    UNIQUE(did)
);
