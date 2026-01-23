import {
  BrowserOAuthClient,
  buildAtprotoLoopbackClientMetadata,
  oauthClientMetadataSchema,
} from '@atproto/oauth-client-browser'
import { ENV, HANDLE_RESOLVER_URL } from './constants.ts'
import clientMetadata from '../oauth-client-metadata.json' with { type: 'json' }

// If the current page's origin is not included in the registered redirect URIs,
// we assume we're running in a development environment and use the loopback
// redirect URI helper create a development client.
const useDevelopmentClient =
  ENV === 'test' ||
  (ENV === 'development' &&
    clientMetadata.redirect_uris.every(
      (u: string) => new URL(u).origin !== window.location.origin,
    ))

export const oauthClient = new BrowserOAuthClient({
  handleResolver: HANDLE_RESOLVER_URL,
  clientMetadata: useDevelopmentClient
    ? buildAtprotoLoopbackClientMetadata({
        scope: clientMetadata.scope,
        redirect_uris: [`${window.location.origin}${window.location.pathname}`],
      })
    : oauthClientMetadataSchema.parse(clientMetadata),
})
