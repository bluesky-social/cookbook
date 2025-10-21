import { useCallback, useEffect, useState } from 'react'
import { Button, Text, TextInput, View } from 'react-native'

export function SignInForm({
  signIn,
  disabled = !signIn,
}: {
  signIn?: (input: string) => Promise<void>
  disabled?: boolean
}) {
  const [input, setInput] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => setError(null), [input])

  const fixedInput = fixInput(input)

  const doSignIn = useCallback(
    async (input: string | null) => {
      setError(null)
      if (disabled || !signIn || !input) return
      try {
        await signIn(input)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      }
    },
    [disabled, signIn]
  )

  return (
    <View
      style={{
        flex: 1,
        gap: 10,
        padding: 10,
        justifyContent: 'center',
        alignItems: 'stretch',
        alignSelf: 'center',
        maxWidth: 400,
      }}
    >
      <Text style={{ fontWeight: 'bold', fontSize: 18 }}>
        Login with the Atmosphere
      </Text>
      <Text>Enter your handle to continue</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <TextInput
          style={{
            borderWidth: 1,
            borderColor: '#ccc',
            padding: 7,
            marginRight: 5,
            minWidth: 200,
            flexGrow: 1,
            flexShrink: 1,
            flexBasis: 1,
          }}
          value={input}
          onChangeText={setInput}
          autoCapitalize="none"
          autoCorrect={false}
          autoFocus
          editable={!disabled}
          placeholder="@alice.example.com"
          submitBehavior="blurAndSubmit"
          onSubmitEditing={() => doSignIn(fixedInput)}
        />
        <Button
          title="Login"
          disabled={disabled}
          onPress={() => doSignIn(fixedInput)}
        />
      </View>
      <Text>
        If you&apos;re a Bluesky user, you already have an Atmosphere account.
      </Text>
      <Button
        title="Create account with Bluesky Social"
        disabled={disabled}
        onPress={() => doSignIn('https://bsky.social')}
      />
      {error ? <Text style={{ color: 'red' }}>{error}</Text> : null}
    </View>
  )
}

function fixInput(input: string) {
  const trimmed = input.replaceAll(' ', '')
  if (trimmed.length < 3) return null // definitely invalid
  if (!trimmed.includes('.')) return null // definitely invalid
  return trimmed
}
