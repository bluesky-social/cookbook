import { JSX } from 'react'
import { Button } from '../components/Button.tsx'
import { SIGN_UP_URL } from '../constants.ts'
import { useOAuthContext } from './OAuthProvider.tsx'
import { OAuthSignInForm } from './OAuthSignInForm.tsx'

export function OAuthSignIn({
  role = 'dialog',
  ...props
}: JSX.IntrinsicElements['div']) {
  const { isLoading, signIn } = useOAuthContext()

  return (
    <div role={role} {...props}>
      <h2 className="text-center text-2xl font-medium">
        Login with the Atmosphere
      </h2>
      <p>Enter your handle to continue</p>

      <OAuthSignInForm
        signIn={signIn}
        disabled={isLoading}
        placeholder="@alice.example.com"
      />

      <Button
        type="button"
        loading={isLoading}
        size="large"
        action={() => signIn(SIGN_UP_URL)}
      >
        Login or signup with {new URL(SIGN_UP_URL).host}
      </Button>
    </div>
  )
}
