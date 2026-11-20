import { AtpAgent } from "@atproto/api";
import "node:process";

// Create an AT Protocol Agent
const agent = new AtpAgent({
  service: "https://bsky.social",
});

async function main() {
  try {
    // We just need to log in...
    await agent.login({
      identifier: process.env.BLUESKY_HANDLE!,
      password: process.env.BLUESKY_PASSWORD!,
    });
    console.log("Successfully logged in!");

    // Now we can make our post!
    await agent.post({
      text: "Hello, world! 🦋",
    });
    console.log("Successfully posted!");
    // Et voilà!
  } catch (err: any) {
    console.error("Uh oh! %s", err.message);
  }
}

main();
