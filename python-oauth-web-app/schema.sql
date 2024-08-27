
CREATE TABLE IF NOT EXISTS oauth_auth_request (
    state TEXT NOT NULL PRIMARY KEY,
    authserver_iss TEXT NOT NULL,
    did TEXT,
    handle TEXT,
    pds_url TEXT,
    pkce_verifier TEXT NOT NULL,
    scope TEXT NOT NULL,
    dpop_authserver_nonce TEXT NOT NULL,
    dpop_private_jwk TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_session (
    did TEXT NOT NULL PRIMARY KEY,
    handle TEXT,
    pds_url TEXT NOT NULL,
    authserver_iss TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    dpop_authserver_nonce TEXT NOT NULL,
    dpop_pds_nonce TEXT,
    dpop_private_jwk TEXT NOT NULL
);
