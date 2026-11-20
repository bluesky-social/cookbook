import { OAuthProvider } from './auth/OAuthProvider.tsx'
import { Authenticated } from './Authenticated.tsx'
import { Home } from './Home.tsx'
import { oauthClient } from './oauthClient.ts'

export function App() {
  return (
    <OAuthProvider client={oauthClient}>
      <Authenticated>
        <Home />
      </Authenticated>
    </OAuthProvider>
  )
}
