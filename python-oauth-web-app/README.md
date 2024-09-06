# OAuth Web Service with Python

This is a example project showing how to implement an Python web service which uses atproto OAuth for authentication. It uses Flask as a web framework, and sqlite as a database to store session tokens.

There is currently a version of this deployed at <https://oauth-flask.demo.bsky.dev/>, though this may not be maintained long-term.


## Quickstart

This demo is designed to be run on the public web, with a globally routed domain name with a valid HTTPS certificate. It uses `rye` to manage dependencies and requires some pre-configuration.

Install `rye` and set up the environment:

```bash
rye sync
```

Copy `example.env` to `.env` and update it with locally-generated secrets:

```bash
# FLASK_SECRET_KEY (for cookie session security)
rye run python3 -c 'import secrets; print(secrets.token_hex())'

# FLASK_CLIENT_SECRET_JWK (for OAuth confidential client)
rye run python3 generate_jwk.py
```

Run the service locally (note that OAuth authorization won't actually work from `localhost` for this project):

```bash
rye run flask run
```

Open a public internet tunnel with a valid hostname and HTTPS using a tool like `ngrok`, Tailscale Funnel, or open-source equivalents:

```bash
ngrok http http://localhost:5000
```

Alternatively, run this on a real server and use Caddy or nginx+certbot to generate TLS certificates.
