# Bluesky Bot Tutorial

This folder contains a starter template for creating a bot on Bluesky. In this example, the bot posts a smiley emoji on an automated schedule once every three hours.

## Set Up

1. Install Typescript: `npm i -g typescript`
2. Install Node.js: `npm i -g ts-node`
3. Make a copy of the example `.env` file by running: `cp example.env .env`. Set your username and password in `.env`. Use an App Password.
4. Compile your project by running: `npx tsc` or activate watch mode to have your code automatically compile: `npx tsc -w`

## Running the script 
1. You can run the script locally: `node index.js`. You should see a smiley emoji posted to your Bluesky account. 
2. Modify the script however you like to make this bot your own! 

## Deploying your bot
1. You can deploy a simple bot for free or low cost on a variety of platforms. For example, check out [Heroku](https://devcenter.heroku.com/articles/github-integration) or [Fly.io](https://fly.io/docs/reference/fly-launch/).

