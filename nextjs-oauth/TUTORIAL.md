# AT Protocol OAuth with Next.js

Build a Next.js app with AT Protocol OAuth authentication.

**What you'll build:** A Next.js application where users can log in with their AT Protocol identity using OAuth.

See this up and running at: https://nextjs-oauth-tutorial.up.railway.app/

---

## Prerequisites

- Node.js 22+
- pnpm (or npm/yarn)
- Basic familiarity with Next.js and TypeScript

---

## Part 1: Project Setup

### 1.1 Create Next.js App

```bash
npx create-next-app@latest my-app --yes
cd my-app
```

### 1.2 Install Dependencies

```bash
pnpm add @atproto/oauth-client-node
```

That's it for now! We'll add more dependencies later.

### 1.3 Run App
```bash
pnpm dev
```

Run your Next app in hot reload mode. Open it in the browser at `http://127.0.0.1:3000`. Be sure to use `127.0.0.1` as opposed to `localhost`. This will be important for the oauth redirect flow.

---

## Part 2: Basic OAuth (Localhost)

Let's get OAuth working with the simplest possible setup: a local loopback client with in-memory storage.

Specifically we'll be using a [confidential client](https://atproto.com/specs/oauth#types-of-clients). Our Next server will hold credentials for talking to a user's PDS. Our server will verify incoming requests from the browser using cookies for session auth.

### 2.1 OAuth Client

Create `lib/auth/client.ts`:

```typescript
import {
  NodeOAuthClient,
  buildAtprotoLoopbackClientMetadata,
} from "@atproto/oauth-client-node";
import type {
  NodeSavedSession,
  NodeSavedState,
} from "@atproto/oauth-client-node";

export const SCOPE = "atproto";

// Use globalThis to persist across Next.js hot reloads
const globalAuth = globalThis as unknown as {
  stateStore: Map<string, NodeSavedState>;
  sessionStore: Map<string, NodeSavedSession>;
};
globalAuth.stateStore ??= new Map();
globalAuth.sessionStore ??= new Map();

let client: NodeOAuthClient | null = null;

export async function getOAuthClient(): Promise<NodeOAuthClient> {
  if (client) return client;

  client = new NodeOAuthClient({
    clientMetadata: buildAtprotoLoopbackClientMetadata({
      scope: SCOPE,
      redirect_uris: ["http://127.0.0.1:3000/oauth/callback"],
    }),
  
    stateStore: {
      async get(key: string) {
        return globalAuth.stateStore.get(key);
      },
      async set(key: string, value: NodeSavedState) {
        globalAuth.stateStore.set(key, value);
      },
      async del(key: string) {
        globalAuth.stateStore.delete(key);
      },
    },

    sessionStore: {
      async get(key: string) {
        return globalAuth.sessionStore.get(key);
      },
      async set(key: string, value: NodeSavedSession) {
        globalAuth.sessionStore.set(key, value);
      },
      async del(key: string) {
        globalAuth.sessionStore.delete(key);
      },
    },
  });

  return client;
}
```

The `globalThis` pattern is a standard Next.js technique for persisting data across hot module reloads in development. Without this, the in-memory stores would be wiped every time you edit a file.

AT Protocol OAuth has a special carveout for local development. The `client_id` must be `localhost` and the `redirect_uri` must be on host `127.0.0.1`. Read more [here](https://atproto.com/specs/oauth#localhost-client-development).

**Key concepts:**
- `buildAtprotoLoopbackClientMetadata` - Helper for special client type used in localhost development 
- `stateStore` - Temporary storage during OAuth flow (CSRF protection)
- `sessionStore` - Persistent sessions keyed by user's DID

### 2.2 Session Helper

Create `lib/auth/session.ts`:

```typescript
import { cookies } from "next/headers";
import { getOAuthClient } from "./client";
import type { OAuthSession } from "@atproto/oauth-client-node";

export async function getSession(): Promise<OAuthSession | null> {
  const did = await getDid();
  if (!did) return null;

  try {
    const client = await getOAuthClient();
    return await client.restore(did);
  } catch {
    return null;
  }
}

export async function getDid(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get("did")?.value ?? null;
}
```

### 2.3 Login Route

Create `app/oauth/login/route.ts`:

This route initiates the login flow. We only need the user's handle. We'll then resolve the user's Authorization Server (their PDS) and redirect them there.

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getOAuthClient, SCOPE } from "@/lib/auth/client";

export async function POST(request: NextRequest) {
  try {
    const { handle } = await request.json();

    if (!handle || typeof handle !== "string") {
      return NextResponse.json(
        { error: "Handle is required" },
        { status: 400 }
      );
    }

    const client = await getOAuthClient();

    // Resolves handle, finds their auth server, returns authorization URL
    const authUrl = await client.authorize(handle, {
      scope: SCOPE,
    });

    return NextResponse.json({ redirectUrl: authUrl.toString() });
  } catch (error) {
    console.error("OAuth login error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Login failed" },
      { status: 500 }
    );
  }
}
```

### 2.4 Callback Route

After a user approves the authorization consent screen, they'll be redirected to this callback route. We'll exchange the code from the redirect for actual credentials. We'll then set a cookie for the user's DID.

Create `app/oauth/callback/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getOAuthClient } from "@/lib/auth/client";

const PUBLIC_URL = process.env.PUBLIC_URL || "http://127.0.0.1:3000";

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams;
    const client = await getOAuthClient();

    // Exchange code for session
    const { session } = await client.callback(params);

    const response = NextResponse.redirect(new URL("/", PUBLIC_URL));

    // Set DID cookie
    response.cookies.set("did", session.did, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 7, // 1 week
      path: "/",
    });

    return response;
  } catch (error) {
    console.error("OAuth callback error:", error);
    return NextResponse.redirect(new URL("/?error=login_failed", PUBLIC_URL));
  }
}
```

We use `PUBLIC_URL` with a fallback to `127.0.0.1:3000` to ensure we always redirect to the correct host. This avoids cookie issues that arise from localhost vs 127.0.0.1 mismatches.

### 2.5 Logout Route

To logout, we want to delete the cookie and revoke the current Oauth session for the user.

Create `app/oauth/logout/route.ts`:

```typescript
import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getOAuthClient } from "@/lib/auth/client";

export async function POST() {
  try {
    const cookieStore = await cookies();
    const did = cookieStore.get("did")?.value;

    if (did) {
      const client = await getOAuthClient();
      await client.revoke(did);
    }

    cookieStore.delete("did");
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Logout error:", error);
    const cookieStore = await cookies();
    cookieStore.delete("did");
    return NextResponse.json({ success: true });
  }
}
```

### 2.6 Client Metadata Route

This route exposes the OAuth client metadata at a well-known URL. It's useful for debugging and required for production OAuth.

Create `app/oauth-client-metadata.json/route.ts`:

```typescript
import { getOAuthClient } from "@/lib/auth/client";
import { NextResponse } from "next/server";

// The URL of this endpoint IS your client_id
// Authorization servers fetch this to learn about your app

export async function GET() {
  const client = await getOAuthClient();
  return NextResponse.json(client.clientMetadata);
}
```

You can visit `http://127.0.0.1:3000/oauth-client-metadata.json` to see your client configuration.

### 2.7 Login Form Component

Create `components/LoginForm.tsx`:

```typescript
"use client";

import { useState } from "react";

export function LoginForm() {
  const [handle, setHandle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/oauth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Login failed");
      }

      // Redirect to authorization server
      window.location.href = data.redirectUrl;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
          Handle
        </label>
        <input
          type="text"
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
          placeholder="user.example.com"
          className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
          disabled={loading}
        />
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={loading || !handle}
        className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}
```

### 2.8 Logout Button Component

Create `components/LogoutButton.tsx`:

```typescript
"use client";

import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/oauth/logout", { method: "POST" });
    router.refresh();
  }

  return (
    <button
      onClick={handleLogout}
      className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
    >
      Sign out
    </button>
  );
}
```

### 2.9 Update Home Page

Replace `app/page.tsx`:

```typescript
import { getSession } from "@/lib/auth/session";
import { LoginForm } from "@/components/LoginForm";
import { LogoutButton } from "@/components/LogoutButton";

export default async function Home() {
  const session = await getSession();

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <main className="w-full max-w-md mx-auto p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
            AT Protocol OAuth
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400">
            Sign in with your AT Protocol account
          </p>
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          {session ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  Signed in as{" "}
                  <span className="font-mono">{session.did}</span>
                </p>
                <LogoutButton />
              </div>
              <p className="text-green-600">Authentication working!</p>
            </div>
          ) : (
            <LoginForm />
          )}
        </div>
      </main>
    </div>
  );
}
```

### Checkpoint: Test OAuth

Your app should already be running from Part 1. If not:

```bash
pnpm dev
```

1. Open http://127.0.0.1:3000 (_not_ localhost)
2. Enter your handle
3. Authorize the app
4. You should see "Authentication working!" with your DID

---

## Part 3: Add Database Persistence

The in-memory approach works for local development, but for production you'll want a proper database. Let's add SQLite.

### 3.1 Install Database Dependencies

```bash
pnpm add better-sqlite3 kysely
pnpm add -D @types/better-sqlite3 tsx
```

**What these do:**
- `better-sqlite3` - Fast SQLite driver
- `kysely` - Type-safe SQL query builder
- `tsx` - Run TypeScript files directly (for scripts)

### 3.2 Update next.config.ts

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["better-sqlite3"],
};

export default nextConfig;
```

This tells Next.js to use the native SQLite module server-side.

### 3.3 Database Connection

Create `lib/db/index.ts`:

```typescript
import Database from "better-sqlite3";
import { Kysely, SqliteDialect } from "kysely";

const DATABASE_PATH = process.env.DATABASE_PATH || "app.db";

let _db: Kysely<DatabaseSchema> | null = null;

export const getDb = (): Kysely<DatabaseSchema> => {
  if (!_db) {
    const sqlite = new Database(DATABASE_PATH);
    sqlite.pragma("journal_mode = WAL");

    _db = new Kysely<DatabaseSchema>({
      dialect: new SqliteDialect({ database: sqlite }),
    });
  }
  return _db;
};

export interface DatabaseSchema {
  auth_state: AuthStateTable;
  auth_session: AuthSessionTable;
}

interface AuthStateTable {
  key: string;
  value: string;
}

interface AuthSessionTable {
  key: string;
  value: string;
}
```

### 3.4 Create Migrations

Create `lib/db/migrations.ts`:

```typescript
import { Kysely } from "kysely";
import { Migrator } from "kysely/migration";
import type { Migration } from "kysely/migration";
import { getDb } from ".";

const migrations: Record<string, Migration> = {
  "001": {
    async up(db: Kysely<unknown>) {
      await db.schema
        .createTable("auth_state")
        .addColumn("key", "text", (col) => col.primaryKey())
        .addColumn("value", "text", (col) => col.notNull())
        .execute();

      await db.schema
        .createTable("auth_session")
        .addColumn("key", "text", (col) => col.primaryKey())
        .addColumn("value", "text", (col) => col.notNull())
        .execute();
    },
    async down(db: Kysely<unknown>) {
      await db.schema.dropTable("auth_session").execute();
      await db.schema.dropTable("auth_state").execute();
    },
  },
};

export function getMigrator() {
  const db = getDb();
  return new Migrator({
    db,
    provider: {
      getMigrations: async () => migrations,
    },
  });
}
```

### 3.5 Migration Script

Create `scripts/migrate.ts`:

```typescript
import { getMigrator } from "@/lib/db/migrations";

async function main() {
  const migrator = getMigrator();
  const { error } = await migrator.migrateToLatest();
  if (error) throw error;
  console.log("Migrations complete.");
}

main();
```

### 3.6 Update package.json Scripts

```json
{
  "scripts": {
    "dev": "pnpm migrate && next dev",
    "build": "next build",
    "start": "pnpm migrate && next start",
    "migrate": "tsx scripts/migrate.ts"
    "lint": "eslint"
  }
}
```

### 3.7 Update OAuth Client to Use Database

Update the following sections in `lib/auth/client.ts`:

```typescript
{
  stateStore: {
    async get(key: string) {
      const db = getDb();
      const row = await db
        .selectFrom("auth_state")
        .select("value")
        .where("key", "=", key)
        .executeTakeFirst();
      return row ? JSON.parse(row.value) : undefined;
    },
    async set(key: string, value: NodeSavedState) {
      const db = getDb();
      const valueJson = JSON.stringify(value);
      await db
        .insertInto("auth_state")
        .values({ key, value: valueJson })
        .onConflict((oc) => oc.column("key").doUpdateSet({ value: valueJson }))
        .execute();
    },
    async del(key: string) {
      const db = getDb();
      await db.deleteFrom("auth_state").where("key", "=", key).execute();
    },
  },

  sessionStore: {
    async get(key: string) {
      const db = getDb();
      const row = await db
        .selectFrom("auth_session")
        .select("value")
        .where("key", "=", key)
        .executeTakeFirst();
      return row ? JSON.parse(row.value) : undefined;
    },
    async set(key: string, value: NodeSavedSession) {
      const db = getDb();
      const valueJson = JSON.stringify(value);
      await db
        .insertInto("auth_session")
        .values({ key, value: valueJson })
        .onConflict((oc) => oc.column("key").doUpdateSet({ value: valueJson }))
        .execute();
    },
    async del(key: string) {
      const db = getDb();
      await db.deleteFrom("auth_session").where("key", "=", key).execute();
    },
  }
}

```

You can also delete the `globalAuth` memory store at the top of the file.

### Checkpoint: Test with Database

```bash
pnpm dev
```

You should see "Migrations complete." and an `app.db` file created. Now you can edit files during the OAuth flow without losing state!

---

## Part 4: Production Deployment

For production, you need a "confidential client" instead of the loopback client. This requires:
- A public URL
- A private key for signing
- Public endpoints for client metadata and JWKS

### 4.1 Environment Variables

For production, you'll need:

```env
PUBLIC_URL=https://your-app.example.com
PRIVATE_KEY={"kty":"EC","kid":"...","alg":"ES256",...}
```

### 4.2 Generate Private Key

Create `scripts/gen-key.ts`:

```typescript
import { JoseKey } from "@atproto/oauth-client-node";

async function main() {
  const kid = Date.now().toString();
  const key = await JoseKey.generate(["ES256"], kid);
  console.log(JSON.stringify(key.privateJwk));
};

main();
```

Add to scripts in `package.json`:

```json
"gen-key": "tsx scripts/gen-key.ts"
```

Run `pnpm gen-key` and save the output as `PRIVATE_KEY` env var.

### 4.3 JWKS Endpoint

This is a .well-known endpoint that advertises your client's public key

Create `app/.well-known/jwks.json/route.ts`:

```typescript
import { NextResponse } from "next/server";
import { JoseKey } from "@atproto/oauth-client-node";

// Serves the public keys for the OAuth client
// Required for confidential clients using private_key_jwt authentication

const PRIVATE_KEY = process.env.PRIVATE_KEY;

export async function GET() {
  if (!PRIVATE_KEY) {
    return NextResponse.json({ keys: [] });
  }

  const key = await JoseKey.fromJWK(JSON.parse(PRIVATE_KEY));
  return NextResponse.json({
    keys: [key.publicJwk],
  });
}
```

### 4.4 Update OAuth Client for Production

Update `lib/auth/client.ts` the actual metadata for your confidential client:

```typescript
import {
  JoseKey,
  Keyset,
  NodeOAuthClient,
  buildAtprotoLoopbackClientMetadata,
} from "@atproto/oauth-client-node";
import type {
  NodeSavedSession,
  NodeSavedState,
  OAuthClientMetadataInput,
} from "@atproto/oauth-client-node";
import { getDb } from "../db";

export const SCOPE = "atproto";

let client: NodeOAuthClient | null = null;

const PUBLIC_URL = process.env.PUBLIC_URL;
const PRIVATE_KEY = process.env.PRIVATE_KEY;

function getClientMetadata(): OAuthClientMetadataInput {
  if (PUBLIC_URL) {
    return {
      client_id: `${PUBLIC_URL}/oauth-client-metadata.json`,
      client_name: "OAuth Tutorial",
      client_uri: PUBLIC_URL,
      redirect_uris: [`${PUBLIC_URL}/oauth/callback`],
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      scope: SCOPE,
      token_endpoint_auth_method: "private_key_jwt" as const,
      token_endpoint_auth_signing_alg: "ES256" as const, // must match the alg in scripts/gen-key.ts
      jwks_uri: `${PUBLIC_URL}/.well-known/jwks.json`,
      dpop_bound_access_tokens: true,
    };
  } else {
    return buildAtprotoLoopbackClientMetadata({
      scope: SCOPE,
      redirect_uris: ["http://127.0.0.1:3000/oauth/callback"],
    });
  }
}

async function getKeyset(): Promise<Keyset | undefined> {
  if (PUBLIC_URL && PRIVATE_KEY) {
    return new Keyset([await JoseKey.fromJWK(JSON.parse(PRIVATE_KEY))]);
  } else {
    return undefined;
  }
}

export async function getOAuthClient(): Promise<NodeOAuthClient> {
  if (client) return client;

  client = new NodeOAuthClient({
    clientMetadata: getClientMetadata(),
    keyset: await getKeyset(),
    ...
```

You can read more about the client metadata doc here: https://atproto.com/specs/oauth#client-id-metadata-document

### Checkpoint: Test Confidential Client

To test your confidential client, you'll need to deploy it somewhere. We've included a simple deploy guide for Railway in [RAILWAY_DEPLOY.md](./RAILWAY_DEPLOY.md)

---

## Part 5: Requesting Scopes (Bonus)

By default, we request only the `atproto` scope. The `atproto` scope is required and offers basic authentication for an atproto identity, however it does not authorize the client to access any privileged information or perform any actions on behalf of the user.

You can request more specific scopes to expand what your app can do.

### 5.1 Available Scopes

AT Protocol OAuth supports several scope patterns. Full documentation on OAuth scopes can be found here: https://atproto.com/specs/permission

A few examples:

- `atproto` - Basic authentication (required)
- `account:email` - Access the users email (they will have the option to opt out in the consent screen)
- `repo:com.example.record` - Write access to all `com.example.record` records

### 5.2 Update the SCOPE Constant

To change the requested scope, simply update the `SCOPE` constant in `lib/auth/client.ts`. It should be a space-delimited string.

```typescript
export const SCOPE = "atproto account:email repo:com.example.record";
```

This constant is used in three places:
- The loopback client metadata (for local development)
- The production client metadata
- The login route's authorize call

By centralizing it in one constant, you only need to change it in one place.

### Checkpoint: Requesting Scopes

1. Run your app with `pnpm dev`
2. Open http://127.0.0.1:3000 (_not_ localhost)
3. Go throught he authorization flow
4. On the consent screen of your authorization server, you should see that the app is requesting read access to your email as well as access to your repository
