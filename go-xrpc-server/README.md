
# XRPC API Server Example (Go)

This is a minimal Go API service showing how to use the indigo SDK's auth middleware for authentication. For a broader introduction to XRPC HTTP APIs in atproto, see https://atproto.com/specs/xrpc

The server implements the following XRPC procedure (HTTP POST) endpoints:

- `dev.atbin.xrpc.echo`: takes an `input` field from request JSON body, and returns it in `output` field of response JSON body. Does not require authentication.
- `dev.atbin.xrpc.echoAuthRequired`: variant which requires inter-service auth (eg, from PDS proxying)
- `dev.atbin.xrpc.echoAuthOptional`: variant where inter-service auth is optional. If auth header is provided, it must be valid, but if header is not present the request succeeds. The `did` field in reponse JSON body indicates authenticated account DID (if present)
- `dev.atbin.xrpc.echoAdmin`: variant where admin password auth is required (aka, HTTP Basic authentication with username "admin" and a password).

The server also serves a stub `did:web` document for the current hostname, with a `#demo` service endpoint registered.

## Getting the Code

```
git clone https://github.com/bluesky-social/cookbook
cd cookbook/go-xrpc-server/
```


## Usage

The process is expected to run with a valid public internet hostname and HTTPS/TLS certificate. Localhost/offline is not supported. A tunneling service like [ngrok.com](https://ngrok.com/) can be used for experimentation:

```shell
ngrok http http://localhost:8080
```

This will return a random hostname like `b470-example.ngrok-free.app`. Use this to construct a `did:web` identity like `did:web:b470-example.ngrok-free.app`.

Compile and run the example code, providing the DID as an argument:

```shell
go run . --service-did did:web:b470-example.ngrok-free.app
```

You can test the public echo endpoint using [HTTPie](https://httpie.io/):

```shell
http post https://b470-example.ngrok-free.app/xrpc/dev.atbin.xrpc.echo input=hello
```

You can test the authenticated endpoints using PDS service proxying using [goat](https://github.com/bluesky-social/goat):

```shell
# public endpoint
goat xrpc post https://b470-example.ngrok-free.app dev.atbin.xrpc.echo input=123

# authenticated (requires 'goat account login')
goat xrpc post did:web:b470-example.ngrok-free.app#demo dev.atbin.xrpc.echoAuthRequired input=123

# admin endpoint
ADMIN_PASSWORD=dummy123 goat xrpc post https://b470-example.ngrok-free.app dev.atbin.xrpc.echoAdmin input=123
```
