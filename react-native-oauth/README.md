# React-native (Expo) OAuth based Atmosphere Client Starter

This is an [Expo](https://expo.dev) project created with [`create-expo-app`](https://www.npmjs.com/package/create-expo-app), and adapted to include a starter template for building Atmosphere apps, with OAuth authentication using the [@atproto/oauth-client-expo](https://www.npmjs.com/package/@atproto/oauth-client-expo) library, based on the [Authentication in Expo Router](https://docs.expo.dev/router/advanced/authentication/) guide.

## Get started

1. Install dependencies

   ```bash
   npm install
   ```

2. Start the app

   ```bash
   npx expo start
   ```

In the output, you'll find options to open the app in a

- [development build](https://docs.expo.dev/develop/development-builds/introduction/)
- [Android emulator](https://docs.expo.dev/workflow/android-studio-emulator/)
- [iOS simulator](https://docs.expo.dev/workflow/ios-simulator/)
- [Expo Go](https://expo.dev/go), a limited sandbox for trying out app development with Expo

You can start developing by editing the files inside the **app** directory. This project uses [file-based routing](https://docs.expo.dev/router/introduction).

## Usage

### Serve your `oauth-client-metadata.json`

You will need to serve an `oauth-client-metadata.json` from your application's website. An example of this metadata would look like this:

```json
{
  "client_id": "https://app.example.com/assets/oauth-client-metadata.json",
  "client_name": "React Native OAuth Client Demo",
  "client_uri": "https://app.example.com",
  "redirect_uris": [
    "https://app.example.com/sign-in",
    "com.example.app:/sign-in"
  ],
  "scope": "atproto account:email rpc:*?aud=did:web:api.bsky.app#bsky_appview",
  "token_endpoint_auth_method": "none",
  "response_types": ["code"],
  "grant_types": ["authorization_code", "refresh_token"],
  "application_type": "native",
  "dpop_bound_access_tokens": true
}
```

- The `client_id` should be the **exact same URL** as where you are serving your `oauth-client-metadata.json` from
- The `client_uri` can be the home page of where you are serving your metadata from
- Your `redirect_uris` should contain a native redirect URI. The scheme must be formatted as the _reverse_ of the domain you are serving the metadata from. For example, if the client metadata document is served from `https://app.example.com/assets/oauth-client-metadata.json`, then the redirect URI should be `com.example.app:/sign-in`. The scheme _must_ contain _only one trailing slash_ after the `:`. `com.example.app://sign-in` would be invalid. The path component must be `/sign-in` to match this example project.
- The `application_type` must be `native`
- `scope` should be adjusted to your app's needs. Do not use `transition:*` scopes as they will become rejected in the future.

For a real-world example, see [Skylight's client metadata](https://skylight.expo.app/oauth/client-metadata.json).

For more information about client metadata, see [the Atproto documentation](https://atproto.com/specs/oauth#client-id-metadata-document).

### Configure the OAuth client

The `ExpoOAuthClient` client is configured in `utils/oauthClient.ts`. Make sure that the `clientMetadata` object matches the content of the `oauth-client-metadata.json` you are serving.

The `handleResolver` can be set to any service that supports the `com.atproto.identity.resolveHandle` method. It is recommended to use a service under your control for improved privacy for your users. Alternatively, you can use a public resolver such as `https://bsky.social`.

### Sign a user in

The `SessionContext` context provides a `signIn(input)` method that can be used to sign a user in. The `SignInForm` component in `components/SignInForm.tsx` provides a simple UI for signing in with a handle.

`input` must be one of the following:

- A valid Atproto user handle, e.g. `hailey.bsky.team` or `hailey.at`
- A valid DID, e.g. `did:web:hailey.at` or `did:plc:oisofpd7lj26yvgiivf3lxsi`
- A valid PDS host, e.g. `https://cocoon.hailey.at` or `https://bsky.social`

### Making authenticated requests

Once a user is signed in, you can create an `Agent` instance using the OAuth session.

The `PdsAgentProvider` component in `components/PdsAgentProvider.tsx` demonstrates how to create an `Agent` that can be used to make authenticated requests to the user's PDS.

The `BskyAgentProvider` component in `components/BskyAgentProvider.tsx` demonstrates how to create a `BskyAgent` that can be used to interact with a dedicated appview (the Bluesky public API in this case).

An example of using both agents can be found in `app/(authenticated)/index.tsx`.

## Possible improvements

Currently, the `SessionProvider` only stores the latest used account (in order to restore the session on app restart). This could be improved by storing multiple accounts and allowing the user to switch between them.

## Links

The following resources might help you get started:

- [Authentication in Expo Router](https://docs.expo.dev/router/advanced/authentication/): How to implement authentication and protect routes with Expo Router.
- [Expo documentation](https://docs.expo.dev/guides/authentication/): Learn how to utilize the expo-auth-session library to implement authentication with OAuth or OpenID providers. (Note: AT flavoured OAuth is **not** compatible with OpenID Connect).
