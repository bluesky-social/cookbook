# Bluesky Bot Tutorial

This folder contains a starter template for creating a bot on Bluesky. In this example, the bot posts a smiley emoji on an automated schedule once every three hours.

It uses the [`@atproto/lex`](https://github.com/bluesky-social/atproto/tree/main/packages/lex) stack: type-safe Lexicon tooling that generates TypeScript for the records you use. Because the bot authenticates with an App Password, it uses [`@atproto/lex-password-session`](https://github.com/bluesky-social/atproto/tree/main/packages/lex/lex-password-session) to log in and the `Client` from `@atproto/lex` to write the post.

## Set Up

1. Make sure you're on Node.js 24 or newer (`node --version`). The bot runs its TypeScript directly using Node's built-in [type stripping](https://nodejs.org/api/typescript.html), so no transpiler is needed.
2. Install dependencies: `npm install`
3. Make a copy of the example `.env` file: `cp example.env .env`. Set your username and password in `.env`. **Use an [App Password](https://bsky.app/settings/app-passwords)**, not your main account password.

## Running the bot

Run it locally:

```
npm start
```

This regenerates the typed lexicons and then starts the bot. You should see a smiley emoji posted to your Bluesky account, and it will keep posting once every three hours. Modify `index.ts` however you like to make this bot your own!

## How the Lexicon codegen works

The bot talks to Bluesky using generated, type-safe schemas:

- **`lexicons/`** and **`lexicons.json`** (checked in) — the Lexicon JSON for `app.bsky.feed.post` and its dependencies, fetched with `npm run lexicons` (`lex install app.bsky.feed.post`).
- **`src/lexicons/`** (generated, gitignored) — TypeScript produced by `npm run build` (`lex build`). This is what gives `app.bsky.feed.post` its compile-time-checked `text`/`createdAt` fields.

`npm start` runs `npm run build` automatically (via `prestart`), so you never have to generate by hand. To add more record types later, run e.g. `npx lex install app.bsky.feed.like` and rebuild.

Useful scripts:

| Command | What it does |
| --- | --- |
| `npm start` | Generate lexicons, then run the bot |
| `npm run build` | Regenerate `src/lexicons/` from `lexicons/` |
| `npm run typecheck` | Type-check without running (`tsc`) |
| `npm run lexicons` | Re-fetch the Lexicon JSON into `lexicons/` |

## Deploying your bot

You can deploy a simple bot for free or low cost on a variety of platforms. For example, check out [Railway](https://railway.app) or [Fly.io](https://fly.io/docs/reference/fly-launch/).
