# React Single Page App OAuth Client example

This is an example of a React Single Page App (SPA) that uses OAuth to sign in with an [Atproto](https://atproto.com/) identity provider, such as [Skylight](https://skylight.expo.app/) or [Bluesky](https://bsky.app/).

## Get started

1. Install dependencies

   ```bash
   npm install
   ```

2. Start the app (dev mode)

   ```bash
    npm dev
   ```

In the output, you'll find a local URL to open the app in your browser.

## Deploy

To build and deploy the app, run:

```bash
npm run build
```

This will generate the production build in the `dist` directory. You can then serve the contents of this directory using any static file server or deploy it to a hosting service of your choice.

## Usage

### Serve your `oauth-client-metadata.json`

You will need to serve an `oauth-client-metadata.json` from your application's website. An example of this metadata would look like this:

```json
{
  "client_id": "https://app.example.com/oauth-client-metadata.json",
  "client_name": "React SPA AT OAuth Example",
  "client_uri": "https://app.example.com",
  "redirect_uris": ["https://app.example.com/"],
  "scope": "atproto account:email repo:* rpc:*?aud=did:web:api.bsky.app#bsky_appview",
  "token_endpoint_auth_method": "none",
  "response_types": ["code"],
  "grant_types": ["authorization_code", "refresh_token"],
  "application_type": "web",
  "dpop_bound_access_tokens": true
}
```

The build process will bundle the
[`oauth-client-metadata.json`](./oauth-client-metadata.json) file in order to
configure the OAuth client, and generate the corresponding asset when built.

- The `client_id` should be the **exact same URL** as where you are serving your `oauth-client-metadata.json` from
- The `client_uri` can be the home page of where you are serving your metadata from
- Your `redirect_uris` should contain the URL of your SPA where the OAuth client is running
- The `application_type` must be `web` to allow HTTPS redirect URIs
- `scope` should be adjusted to your app's needs. Do not use `transition:*` scopes as they will become rejected in the future.

For more information about client metadata, see [the Atproto documentation](https://atproto.com/specs/oauth#client-id-metadata-document).

> [!NOTE]
>
> In development mode, the app will use a special client id that does not
> require serving the `oauth-client-metadata.json` file from a web server.
>
> This will be done automatically for you when running `npm dev`, unless the
> SPA's origin is contained in the oauth metadata document's `redirect_uris`
> field, allowing to use an externally hosted version of the app for
> development.

### Configure the OAuth client

In the source code, the OAuth client is configured by importing the
`oauth-client-metadata.json` file and passing it to the
`OAuthClientBrowser` constructor in `src/oauthClient.ts`:

```ts
import {
  BrowserOAuthClient,
  oauthClientMetadataSchema,
} from '@atproto/oauth-client-browser'

import clientMetadata from '../oauth-client-metadata.json' with { type: 'json' }

// ...

export const oauthClient = new OAuthClientBrowser({
  // parsing is only needed to make typescript happy
  clientMetadata: oauthClientMetadataSchema.parse(clientMetadata),
  handleResolverUrl: HANDLE_RESOLVER_URL,
})
```

Make sure that the `clientMetadata` object matches the content of the
`oauth-client-metadata.json` you are serving (this is the case by default in this example).

The `handleResolver` can be set to any service that supports the `com.atproto.identity.resolveHandle` XRPC method. It is recommended to use a service under your control for improved privacy for your users. Alternatively, you can use a public resolver such as `https://bsky.social`.

### Making authenticated requests

Once a user is signed in, you can create an `@atproto/api` `Agent` instance using the OAuth session.

This is not demonstrated in this example.
