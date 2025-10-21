This implements a simple atproto OAuth client as a SPA in vanilla JS, using the `@atproto/oauth-client-browser` package.

## Usage

There are no build steps, but an HTTP server is reqired. You can spawn a local one via:

```sh
python3 -m http.server
```

Then, navigate to http://127.0.0.1:8000 in your browser.

## Non-Localhost Deployment

Alongside the app itself, we need to make the client metadata document publicly accessible (so that the Authorization Server can request it during auth). HTTPS is required, with a valid certificate.

Copy `oauth-client-metadata.example.json` to `oauth-client-metadata.json` and edit it to replace all instances of "EXAMPLE.COM" with the hostname of your publicly-reachable web server (The placeholder hostnames are uppercased to make them easier to spot, your actual hostname should not be uppercased!)

This can be done like so:

```sh
sed s/EXAMPLE.COM/my-real-hostname.com/g oauth-client-metadata.example.json > oauth-client-metadata.json
```
