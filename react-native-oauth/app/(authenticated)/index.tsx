import { type AtIdentifierString } from '@atproto/lex'
import { useQuery } from '@tanstack/react-query'
import { Button, Image, Text, View } from 'react-native'
import { app, com } from '@/src/lexicons'
import { useClient } from '@/components/ClientProvider'
import { useOAuthSession, useSession } from '@/components/SessionProvider'

/**
 * Default "index" screen for authenticated users showing profile info.
 */
export default function Index() {
  const session = useOAuthSession()
  const { signOut } = useSession()

  return (
    <View
      style={{
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        gap: 20,
      }}
    >
      <ProfileCard actor={session.did} />
      <AccountInfo />

      <Button onPress={signOut} title="Sign Out" />
    </View>
  )
}

function AccountInfo() {
  const { data, isLoading } = useGetSessionQuery()

  return (
    <View style={{ alignItems: 'center', gap: 2 }}>
      {data ? (
        <>
          <Text>{data.did}</Text>
          <Text>{data.handle}</Text>
          {data.email ? <Text>{data.email}</Text> : null}
        </>
      ) : isLoading ? (
        <Text>Loading...</Text>
      ) : (
        <Text>Failed to load account data</Text>
      )}
    </View>
  )
}

function useGetSessionQuery() {
  const client = useClient()

  return useQuery({
    queryKey: [client.assertDid, 'session'] as const,
    queryFn: async ({ signal }) => {
      // `service: null` opts this call out of the client's appview proxying:
      // getSession is answered by the user's PDS itself.
      return client.call(com.atproto.server.getSession, {}, { signal, service: null })
    },
  })
}

function ProfileCard({ actor }: { actor: AtIdentifierString }) {
  const { data } = useProfileQuery(actor)

  return (
    <View style={{ alignItems: 'center', gap: 2 }}>
      <Image
        source={{ uri: data?.avatar }}
        style={{
          width: 100,
          height: 100,
          borderRadius: 50,
          backgroundColor: 'lightgray',
          marginBottom: 10,
        }}
      />

      <Text style={{ fontSize: 20, fontWeight: 'bold' }}>
        {data?.displayName ?? 'Profile'}
      </Text>

      <Text style={{ color: 'gray' }}>
        {data?.handle ? `@${data.handle}` : actor}
      </Text>

      {data?.description ? (
        <Text style={{ textAlign: 'center' }}>{data.description}</Text>
      ) : null}
    </View>
  )
}

function useProfileQuery(actor: AtIdentifierString) {
  const client = useClient()

  return useQuery({
    queryKey: ['profile', actor] as const,
    queryFn: async ({ signal }) => {
      return client.call(app.bsky.actor.getProfile, { actor }, { signal })
    },
  })
}
