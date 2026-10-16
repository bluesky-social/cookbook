/**
 * Web variant of {@link sessionStore}. `expo-secure-store` is native-only
 * (it wraps the iOS Keychain / Android Keystore and throws on web), so on the
 * web build we persist the "last used account" pointer in `localStorage`.
 *
 * This only stores a DID pointer for session restoration; the actual OAuth
 * session/tokens are managed by the browser OAuth client's own storage.
 */
export const sessionStore = {
  async getItemAsync(key: string): Promise<string | null> {
    return globalThis.localStorage?.getItem(key) ?? null
  },
  async setItemAsync(key: string, value: string): Promise<void> {
    globalThis.localStorage?.setItem(key, value)
  },
  async deleteItemAsync(key: string): Promise<void> {
    globalThis.localStorage?.removeItem(key)
  },
}
