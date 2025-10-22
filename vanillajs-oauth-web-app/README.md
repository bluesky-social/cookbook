# Vanilla JS OAuth Web App Example (SPA)

This implements a simple atproto OAuth client as a SPA in vanilla JS, using the [`@atproto/oauth-client-browser`](https://www.npmjs.com/package/@atproto/oauth-client-browser) package.

## Usage

There are no build steps, but an HTTP server is reqired. You can spawn a local one via:

```sh
python3 -m http.server

# or alternatively:
npx http-server -p 8000
```

Then, navigate to http://127.0.0.1:8000 in your browser.

This is all you need for local testing, but to deploy a public-facing instance, see below.

## Non-Localhost Deployment

Alongside the app itself, we need to make the client metadata document publicly accessible (so that the Authorization Server can request it during auth). HTTPS is required, with a valid certificate.

Copy `oauth-client-metadata.example.json` to `oauth-client-metadata.json` and edit it to replace all instances of "EXAMPLE.COM" with the hostname of your publicly-reachable web server (The placeholder hostnames are uppercased to make them easier to spot, your actual hostname should not be uppercased!)

This can be done like so:

```sh
sed s/EXAMPLE.COM/my-real-hostname.com/g oauth-client-metadata.example.json > oauth-client-metadata.json
```

## How it Works

The implementation is very simple, contained entirely within `index.html` and `main.js`. The OAuth client is configured per the [API documentation](https://github.com/bluesky-social/atproto/tree/main/packages/oauth/oauth-client-browser#readme), with `bsky.social` set as the handle resolution service (which has some [privacy implications](https://github.com/bluesky-social/atproto/tree/main/packages/oauth/oauth-client-browser#handle-resolver)).

The user initiates login by entering their handle. The OAuth SDK resolves the handle and locates the user's PDS, and then redirects the user to the PDS's login page.

The PDS UI will prompt the user to authorize the app to access their account, under the set of [scopes](https://atproto.com/specs/oauth#authorization-scopes) initially requested. If the user accepts, then they'll be redirected back to the application.

Once the OAuth session is established, an `@atproto/api` Agent is instantiated, allowing API requests to be made using the OAuth credentials. In this example, it's used to create a Bluesky post record - see the `doPost()` function.

The rest of the code is just glue to hook things up to the UI elements.
