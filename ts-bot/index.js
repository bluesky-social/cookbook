"use strict";
var __createBinding =
    (this && this.__createBinding) ||
    (Object.create
        ? function (o, m, k, k2) {
              if (k2 === undefined) k2 = k;
              var desc = Object.getOwnPropertyDescriptor(m, k);
              if (
                  !desc ||
                  ("get" in desc
                      ? !m.__esModule
                      : desc.writable || desc.configurable)
              ) {
                  desc = {
                      enumerable: true,
                      get: function () {
                          return m[k];
                      },
                  };
              }
              Object.defineProperty(o, k2, desc);
          }
        : function (o, m, k, k2) {
              if (k2 === undefined) k2 = k;
              o[k2] = m[k];
          });
var __setModuleDefault =
    (this && this.__setModuleDefault) ||
    (Object.create
        ? function (o, v) {
              Object.defineProperty(o, "default", {
                  enumerable: true,
                  value: v,
              });
          }
        : function (o, v) {
              o["default"] = v;
          });
var __importStar =
    (this && this.__importStar) ||
    function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null)
            for (var k in mod)
                if (
                    k !== "default" &&
                    Object.prototype.hasOwnProperty.call(mod, k)
                )
                    __createBinding(result, mod, k);
        __setModuleDefault(result, mod);
        return result;
    };
var __importDefault =
    (this && this.__importDefault) ||
    function (mod) {
        return mod && mod.__esModule ? mod : { default: mod };
    };
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("@atproto/api");
const dotenv = __importStar(require("dotenv"));
const process = __importStar(require("process"));
const puppeteer = __importStar(require("puppeteer"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const crypto_1 = __importDefault(require("crypto")); // for generating unique hashes
dotenv.config();
const COOKIES_PATH = path.join(__dirname, "cookies.json");
const IntervalTime = 1000 * 60; // 1 minute
// Create a Bluesky Agent
const agent = new api_1.BskyAgent({
    service: "https://bsky.social",
});
// Function to load cookies from file
async function loadCookies(page) {
    if (fs.existsSync(COOKIES_PATH)) {
        const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, "utf8"));
        await page.setCookie(...cookies);
        console.log("Cookies loaded from file.");
    }
}
// Function to save cookies to file
async function saveCookies(page) {
    const cookies = await page.cookies();
    fs.writeFileSync(COOKIES_PATH, JSON.stringify(cookies, null, 2));
    console.log("Cookies saved to file.");
}
// Function to scrape the latest tweet text and generate a unique "id"
async function scrapeLatestTweet(username) {
    const browser = await puppeteer.launch({
        headless: false, // Launch with GUI for manual login
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
        const tweetId = crypto_1.default
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
let lastTweetId = null;
async function main() {
    try {
        console.log("Logging into Bluesky...");
        // Login to Bluesky
        await agent.login({
            identifier: process.env.BLUESKY_USERNAME,
            password: process.env.BLUESKY_PASSWORD,
        });
        console.log("Logged into Bluesky successfully.");
        setInterval(async () => {
            console.log("Starting new interval to check for latest tweet...");
            try {
                const tweet = await scrapeLatestTweet(
                    process.env.TWITTER_PROFILE,
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
