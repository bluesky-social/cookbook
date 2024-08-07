
CREATE TABLE IF NOT EXISTS oauth_session (
    state TEXT,
    iss TEXT,
    nonce TEXT,
    pkce_verifier TEXT,
    dpop_private_jwk TEXT
);
