import { ExpoOAuthClient } from '@atproto/oauth-client-expo'

export const oauthClient = new ExpoOAuthClient({
  handleResolver: 'https://bsky.social',
  clientMetadata: require('../oauth-client-metadata.json'),
})
