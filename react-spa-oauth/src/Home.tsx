import { useOAuthContext, useOAuthSession } from './auth/OAuthProvider.tsx'
import { Button } from './components/Button.tsx'
import { Layout } from './components/Layout.tsx'

export function Home() {
  const { signOut } = useOAuthContext()
  const session = useOAuthSession()

  return (
    <Layout>
      <div className="flex flex-grow flex-col items-center justify-center">
        <div className="rounded-md bg-white p-4 flex items-center shadow-md space-x-2">
          <p className="flex-grow">
            Logged in successfully as <code>{session.did}</code>!
          </p>
          <Button onClick={signOut}>Sign Out</Button>
        </div>
      </div>
    </Layout>
  )
}
