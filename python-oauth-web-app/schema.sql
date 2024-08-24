
CREATE TABLE IF NOT EXISTS oauth_auth_request (
    state TEXT NOT NULL PRIMARY KEY,
    authserver_iss TEXT NOT NULL,
    login_hint TEXT,
    did TEXT,
    pds_url TEXT,
    pkce_verifier TEXT NOT NULL,
    dpop_nonce TEXT NOT NULL,
    dpop_private_jwk TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_session (
    did TEXT NOT NULL PRIMARY KEY,
    pds_url TEXT NOT NULL,
    authserver_iss TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    dpop_nonce TEXT NOT NULL,
    dpop_private_jwk TEXT NOT NULL
);
