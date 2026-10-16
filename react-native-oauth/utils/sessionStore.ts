import * as SecureStore from 'expo-secure-store'

/**
 * Small async key/value store used to persist the "last used account" pointer
 * so the session can be restored on the next app start.
 *
 * On native this is backed by `expo-secure-store` (iOS Keychain / Android
 * Keystore). The web build uses the `sessionStore.web.ts` variant instead,
 * since `expo-secure-store` is native-only.
 */
export const sessionStore = {
  getItemAsync: (key: string) => SecureStore.getItemAsync(key),
  setItemAsync: (key: string, value: string) =>
    SecureStore.setItemAsync(key, value),
  deleteItemAsync: (key: string) => SecureStore.deleteItemAsync(key),
}
