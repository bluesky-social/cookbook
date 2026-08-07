import { useEffect, useState } from 'react'
import { useOAuthContext } from './auth/OAuthProvider.tsx'
import { OAuthSignIn } from './auth/OAuthSignIn.tsx'
import { Layout } from './components/Layout.tsx'
import { Spinner } from './components/Spinner.tsx'

export function Authenticated({ children }: { children?: React.ReactNode }) {
  const { isSignedIn, isLoading } = useOAuthContext()
  const [isReady, setIsReady] = useState(!isLoading)

  useEffect(() => {
    if (!isLoading) setIsReady(true)
  }, [isLoading])

  if (isSignedIn) return <>{children}</>

  return (
    <Layout>
      <div className="flex flex-grow flex-col items-center justify-center">
        {isReady ? (
          <OAuthSignIn className="flex w-[450px] max-w-full flex-col items-stretch space-y-4 rounded-md bg-white p-4 shadow-md" />
        ) : (
          <Spinner />
        )}
      </div>
    </Layout>
  )
}
