import {
  TokenRevokedError,
  type ExpoOAuthClientInterface,
  type OAuthSession,
} from '@atproto/oauth-client-expo'
import { sessionStore as store } from '@/utils/sessionStore'
import {
  PropsWithChildren,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

const CURRENT_AUTH_DID = 'oauth_provider-current'

const SessionContext = createContext<{
  session: null | OAuthSession
  isLoading: boolean
  isLoggedIn: boolean
  signIn: (input: string) => Promise<void>
  signOut: () => Promise<void>
}>({
  session: null,
  isLoading: false,
  isLoggedIn: false,
  signIn: async () => {
    throw new Error('AuthContext not initialized')
  },
  signOut: async () => {
    throw new Error('AuthContext not initialized')
  },
})

export function SessionProvider({
  client,
  children,
}: PropsWithChildren<{
  client: ExpoOAuthClientInterface
}>) {
  const [initialized, setInitialized] = useState(false)
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState<null | OAuthSession>(null)

  // Forget our reference to the current session. The atproto client manages its
  // own session storage (and removes a revoked session itself); this only clears
  // the "last used account" pointer we keep to restore the session on restart.
  const forgetSession = useCallback(async () => {
    setSession(null)
    await store.deleteItemAsync(CURRENT_AUTH_DID)
  }, [])

  // Initialize by restoring the previously loaded session, if any.
  useEffect(() => {
    setInitialized(false)
    setSession(null)

    void client
      .handleCallback()
      .then(async (newSession) => {
        if (newSession) return setSession(newSession)

        const lastDid = await store.getItemAsync(CURRENT_AUTH_DID)
        if (!lastDid) return

        // Use "false" as restore argument to allow the app to work off-line
        const restoredSession = await client.restore(lastDid, false)
        setSession(restoredSession)

        // Force a refresh here. If the refresh token was revoked, this throws a
        // TokenRevokedError; the client will have already discarded its stored
        // session, so we just forget our pointer to it.
        await restoredSession.getTokenInfo(true).catch(async (err) => {
          if (err instanceof TokenRevokedError) await forgetSession()
          else throw err
        })
      })
      .catch((err) => {
        console.warn('Error setting up OAuth Session', err)
      })
      .finally(() => {
        setInitialized(true)
        setLoading(false)
      })
  }, [client, forgetSession])

  // When initializing the AuthProvider, we used "false" as restore's refresh
  // argument so that the app can work off-line. The following effect will
  // ensure that the session is pro actively refreshed whenever the app gets
  // back online.
  useEffect(() => {
    if (!session) return

    const check = () => {
      void session.getTokenInfo(true).catch(async (err) => {
        // If the refresh token was revoked (e.g. from another device), the
        // client discards its stored session; forget our pointer to it too.
        if (err instanceof TokenRevokedError) await forgetSession()
        else console.warn('Failed to refresh token', err)
      })
    }

    const interval = setInterval(check, 10 * 60e3)
    return () => clearInterval(interval)
  }, [session, forgetSession])

  const signIn = useCallback(
    async (input: string) => {
      setLoading(true)

      try {
        const session = await client
          .restore(input, true)
          .catch(async (_err) => client.signIn(input))

        setSession(session)
        await store.setItemAsync(CURRENT_AUTH_DID, session.did)
      } finally {
        setLoading(false)
      }
    },
    [client]
  )

  const signOut = useCallback(async () => {
    if (session) {
      setSession(null)
      setLoading(true)
      try {
        await session.signOut()
      } finally {
        setLoading(false)
      }
      await store.deleteItemAsync(CURRENT_AUTH_DID)
    }
  }, [session])

  return (
    <SessionContext.Provider
      value={{
        session,

        isLoading: !initialized || loading,
        isLoggedIn: !!session,

        signIn,
        signOut,
      }}
    >
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  return useContext(SessionContext)
}

export function useOAuthSession(): OAuthSession {
  const { session } = useSession()
  if (!session) throw new Error('User is not logged in')
  return session
}
