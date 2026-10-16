import { PropsWithChildren, createContext, useContext, useMemo } from 'react'
import { Client } from '@atproto/lex'
import { useSession } from './SessionProvider'

const ClientContext = createContext<Client | null>(null)

export function ClientProvider({ children }: PropsWithChildren) {
  const { session } = useSession()

  /**
   * A {@link Client} bound to the user's OAuth session. An `OAuthSession`
   * already satisfies the client's `Agent` interface (it exposes both `did`
   * and `fetchHandler`), so it can be passed straight into
   * `new Client(session)` without any adapter.
   *
   * The `service` option routes requests through the user's PDS to the
   * Bluesky appview (it sets the `atproto-proxy` header). A single client
   * covers both destinations:
   *
   * - Plain xrpc calls made with `client.call(...)` are proxied to the
   *   appview.
   * - Record sugar methods like `client.create(...)` are never proxied and
   *   always target the user's PDS, and any other call can opt out of
   *   proxying with a per-call `service: null` option.
   *
   * @note Proxying requires at least one `rpc:` OAuth scope with
   * `aud=did:web:api.bsky.app#bsky_appview` granted during the OAuth flow,
   * otherwise the PDS will reject any proxying attempts.
   */
  const client = useMemo(() => {
    if (!session) return null
    return new Client(session, { service: 'did:web:api.bsky.app#bsky_appview' })
  }, [session])

  return (
    <ClientContext.Provider value={client}>{children}</ClientContext.Provider>
  )
}

/**
 * Returns the authenticated {@link Client}. Will throw if used outside of an
 * authenticated context. The authenticated user's DID is available via
 * `client.assertDid`.
 */
export function useClient(): Client {
  const client = useContext(ClientContext)
  if (client) return client

  throw new Error('useClient should only be used from authenticated contexts')
}
