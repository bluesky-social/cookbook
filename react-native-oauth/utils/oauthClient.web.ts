import { ExpoOAuthClient } from '@atproto/oauth-client-expo'

/**
 * Web-only development OAuth client.
 *
 * atproto lets a browser app running on a loopback origin use a "localhost"
 * client without hosting an `oauth-client-metadata.json`: the authorization
 * server derives the client metadata from the `http://localhost?...` client_id
 * instead of fetching it. This lets you sign in locally without deploying the
 * metadata document that the native client (see `oauthClient.ts`) requires.
 *
 * IMPORTANT: you must open the app at `http://127.0.0.1:<port>`, NOT
 * `http://localhost:<port>`. atproto requires loopback clients to redirect to
 * the IP address, and the client throws if the current origin uses the
 * "localhost" hostname.
 *
 * This file is only bundled for the web platform (Metro resolves the `.web.ts`
 * variant); native builds use `oauthClient.ts` with the hosted metadata.
 */

// Same scopes the hosted native metadata requests, so the signed-in demo
// screen (appview profile + account email) works identically on web.
const scope = 'atproto account:email rpc:*?aud=did:web:api.bsky.app#bsky_appview'

const redirectUri = `http://127.0.0.1:${window.location.port}/sign-in`

const clientIdUrl = new URL('http://localhost')
clientIdUrl.searchParams.set('redirect_uri', redirectUri)
clientIdUrl.searchParams.set('scope', scope)
const clientId = clientIdUrl.href

export const oauthClient = new ExpoOAuthClient({
  handleResolver: 'https://bsky.social',
  clientMetadata: {
    client_id: clientId,
    scope,
    redirect_uris: [redirectUri],
    response_types: ['code'],
    grant_types: ['authorization_code', 'refresh_token'],
    token_endpoint_auth_method: 'none',
    application_type: 'native',
    dpop_bound_access_tokens: true,
  },
})
