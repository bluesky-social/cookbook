import { BskyAgent } from "@atproto/api";
import * as dotenv from "dotenv";
import * as process from "process";
import * as puppeteer from "puppeteer";
import * as fs from "fs";
import * as path from "path";
import crypto from "crypto"; // for generating unique hashes

dotenv.config();

const COOKIES_PATH = path.join(__dirname, "cookies.json");
const IntervalTime = 1000 * 60; // 1 minute

// Create a Bluesky Agent
const agent = new BskyAgent({
    service: "https://bsky.social",
});

// Function to load cookies from file
async function loadCookies(page: puppeteer.Page) {
    if (fs.existsSync(COOKIES_PATH)) {
        const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, "utf8"));
        await page.setCookie(...cookies);
        console.log("Cookies loaded from file.");
    }
}

// Function to save cookies to file
async function saveCookies(page: puppeteer.Page) {
    const cookies = await page.cookies();
    fs.writeFileSync(COOKIES_PATH, JSON.stringify(cookies, null, 2));
    console.log("Cookies saved to file.");
}

// Function to scrape the latest tweet text and generate a unique "id"
async function scrapeLatestTweet(username: string) {
    const browser = await puppeteer.launch({
        headless: true, // Launch with GUI for manual login
    });
    const page = await browser.newPage();

    // Load session cookies if they exist
    await loadCookies(page);

    try {
        // Navigate to the user's profile
        const profileUrl = `https://twitter.com/${username}`;
        await page.goto(profileUrl, {
            waitUntil: "networkidle2",
            timeout: 60000,
        });

        console.log(`Navigated to profile: ${profileUrl}`);

        // Wait for tweet to be visible, give it a longer timeout in case of slow loading
        await page.waitForSelector("article div[lang]", { timeout: 30000 });

        // Scrape the latest tweet
        const latestTweet = await page.evaluate(() => {
            const tweetElement = document.querySelector("article div[lang]"); // Finds the first tweet on the page
            return tweetElement ? tweetElement.textContent : null;
        });

        // Save session cookies after navigating (for future launches)
        await saveCookies(page);

        await browser.close();

        if (!latestTweet) {
            throw new Error("No tweet found");
        }

        console.log(`Latest tweet: ${latestTweet}`);

        // Generate a hash ID from the tweet text (to simulate an ID)
        const tweetId = crypto
            .createHash("sha256")
            .update(latestTweet)
            .digest("hex");

        return { id: tweetId, text: latestTweet };
    } catch (error) {
        console.error("Error during scraping or page interaction:", error);
        await browser.close();
        throw error;
    }
}

let lastTweetId: string | null = null;

async function main() {
    try {
        console.log("Logging into Bluesky...");
        // Login to Bluesky
        await agent.login({
            identifier: process.env.BLUESKY_USERNAME!,
            password: process.env.BLUESKY_PASSWORD!,
        });
        console.log("Logged into Bluesky successfully.");

        setInterval(async () => {
            console.log("Starting new interval to check for latest tweet...");
            try {
                const tweet = await scrapeLatestTweet(
                    process.env.TWITTER_PROFILE!,
                );

                if (tweet.id !== lastTweetId) {
                    const postContent = tweet.text;
                    console.log(
                        `New tweet found. Tweet ID: ${tweet.id}. Posting to Bluesky...`,
                    );

                    try {
                        // Correct the post format for Bluesky
                        await agent.post({
                            $type: "app.bsky.feed.post", // Specify the type explicitly
                            text: postContent, // Ensure text is correctly passed
                        });
                        console.log(
                            `Successfully posted tweet to Bluesky: "${postContent}"`,
                        );

                        // Update the last posted tweet ID
                        lastTweetId = tweet.id;
                        console.log(`Updated lastTweetId to: ${lastTweetId}`);
                    } catch (error) {
                        console.error("Error while posting to Bluesky:", error);
                    }
                } else {
                    console.log("No new tweet found. Skipping posting.");
                }
            } catch (error) {
                console.error("Error fetching or posting tweet:", error);
            }
        }, IntervalTime);
    } catch (error) {
        console.error("Error logging into Bluesky:", error);
    }
}

main();
