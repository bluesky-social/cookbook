# Deploying to Railway

This guide walks you through deploying your AT Protocol OAuth app to [Railway](https://railway.app).

## Prerequisites

Before deploying, generate a private key for your OAuth client:

```bash
pnpm gen-key
```

Save the output—you'll need it for the environment variables.

## Step 1: Create a New Project

1. Log in to [Railway](https://railway.app) and click **New Project**
2. Select **Deploy from GitHub repo**
3. Paste in your repository URL (or use `https://github.com/bluesky-social/nextjs-oauth-tutorial`)
4. Click **Deploy Repo**

## Step 2: Add a Volume for SQLite

Your app uses SQLite for session storage, which needs persistent disk storage.

1. Right-click on your service and select **Attach Volume**
2. Set the mount path to `/data`

## Step 3: Generate a Domain

1. Click on your service and go to the **Settings** tab
2. In the **Networking** section, click **Generate Domain**
3. Railway should automatically detect that Next.js runs on port 8080, but if not, set the port manually
4. Copy the generated domain (e.g., `your-app-name.up.railway.app`)

## Step 4: Configure Environment Variables

1. Click on your service and go to the **Variables** tab
2. Add the following variables:

| Variable | Value |
|----------|-------|
| `DATABASE_PATH` | `/data/app.db` |
| `PUBLIC_URL` | `https://your-app-name.up.railway.app` |
| `PRIVATE_KEY` | The JSON key from `pnpm gen-key` |

**Important notes:**
- `PUBLIC_URL` must include `https://` and have no trailing slash
- `PRIVATE_KEY` should be the full JSON object (e.g., `{"kty":"EC","kid":"...","crv":"P-256",...}`)

## Step 5: Redeploy

After setting environment variables, Railway will automatically redeploy. Once complete, visit your domain to test the OAuth flow.
