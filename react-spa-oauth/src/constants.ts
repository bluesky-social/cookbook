// Inserted during build
declare const process: { env: { NODE_ENV: string } }

// The current environment. Only "development" and "test" have special meaning.
export const ENV = process.env.NODE_ENV

// The URL of the handle resolver service. It is preferable to use a service you
// control to avoid privacy issues.
export const HANDLE_RESOLVER_URL = 'https://bsky.social'

// The default URL to direct users to sign up for an account.
export const SIGN_UP_URL = 'https://bsky.social'
