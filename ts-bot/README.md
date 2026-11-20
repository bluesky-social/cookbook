# Bluesky Bot Tutorial

This folder contains a starter template for creating a bot on Bluesky. In this example, the bot posts a short message when you run it.

## Setting Up

1. Install [Node.js and npm](https://nodejs.org/en/download/package-manager).
  - Make sure you're up to date; `node -v` should be at least `v20.6.0`!
1. Install Typescript with the command: `npm i -g typescript ts-node`
1. Create the `.env` file by running the command: `npm run setup`
1. Set your handle and password in `.env`. You should use an [App Password](https://bsky.app/settings/app-passwords)!

## Running the Bot

1. Compile and run your bot by running the command: `npm run bot`; you should see "Hello, world! 🦋" posted to your Bluesky account!
1. Modify the script however you like to make this bot your own!

## Deploying Your Bot

You can deploy a simple bot on your own computer. If you want something more, deploying projects like this can be low cost or even free on a variety of platforms. For example, check out:

- [Heroku](https://devcenter.heroku.com/articles/github-integration)
- [Fly.io](https://fly.io/docs/reference/fly-launch/)
