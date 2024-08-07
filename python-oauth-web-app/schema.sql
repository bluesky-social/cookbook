
CREATE TABLE IF NOT EXISTS oauth_request (
    state TEXT,
    iss TEXT,
    did TEXT,
    handle TEXT,
    pds_url TEXT,
    nonce TEXT,
    pkce_verifier TEXT,
    dpop_private_jwk TEXT
);

CREATE TABLE IF NOT EXISTS oauth_session (
    did TEXT,
    handle TEXT,
    pds_url TEXT,
    iss TEXT,
    access_token TEXT,
    refresh_token TEXT,
    dpop_nonce TEXT,
    dpop_private_jwk TEXT
);
