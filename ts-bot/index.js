"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
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
const HASHES_PATH = path.join(__dirname, "lastTweetHashes.json");
const IntervalTime = 1000 * 60; //* 5; // 5 minutes
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
// Function to load the last three tweet hashes from a file
function loadLastTweetHashes() {
    if (fs.existsSync(HASHES_PATH)) {
        return JSON.parse(fs.readFileSync(HASHES_PATH, "utf8"));
    }
    return [];
}
// Function to save the last three tweet hashes to a file
function saveLastTweetHashes(hashes) {
    fs.writeFileSync(HASHES_PATH, JSON.stringify(hashes, null, 2));
    console.log("Last tweet hashes saved to file.");
}
// Function to scrape the latest three tweets and handle quote tweets and image URLs properly
async function scrapeLatestTweets(username) {
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
        // Wait for the tweets to be visible
        await page.waitForSelector("article div[data-testid='tweetText']", {
            timeout: 30000,
        });
        // Scrape the latest three tweets and their quotes if they exist, and also capture image URLs
        const latestTweets = await page.evaluate(() => {
            const tweetElements = Array.from(document.querySelectorAll("article"));
            return tweetElements.slice(0, 3).map((el) => {
                // Main tweet text
                const mainTweetText = el.querySelector("div[data-testid='tweetText']")
                    ?.textContent || "";
                // Check if the tweet contains a quoted tweet (look for nested div with data-testid='tweetText')
                let quotedTweetText = "";
                const quoteElement = el.querySelector("div[aria-labelledby] div[data-testid='tweetText']");
                // Capture the quote, but only if it's not duplicating the main tweet
                if (quoteElement &&
                    quoteElement.textContent !== mainTweetText) {
                    quotedTweetText = `\n\nQuoted tweet: "${quoteElement.textContent}"`;
                }
                // Initialize imageUrls as a string array
                let imageUrls = [];
                // Select image elements and cast to HTMLImageElement to access 'src'
                const imageElements = el.querySelectorAll('img[alt="Image"]');
                if (imageElements.length > 0) {
                    imageUrls = Array.from(imageElements).map((img) => img.src); // Get the src attribute of each image
                }
                // Return the combined main tweet text, quoted tweet text (if any), and image URLs
                return {
                    text: mainTweetText.trim() + quotedTweetText,
                    images: imageUrls, // Attach the array of image URLs
                };
            });
        });
        // Save session cookies after navigating (for future launches)
        await saveCookies(page);
        await browser.close();
        if (latestTweets.length === 0) {
            throw new Error("No tweets found");
        }
        console.log(`Latest tweets: ${JSON.stringify(latestTweets, null, 2)}`);
        // Generate a hash ID from each tweet text (to simulate an ID)
        const tweetData = latestTweets.map((tweet) => ({
            id: crypto_1.default.createHash("sha256").update(tweet.text).digest("hex"),
            text: tweet.text,
            images: tweet.images, // Include the image URLs in the tweet data
        }));
        return tweetData;
    }
    catch (error) {
        console.error("Error during scraping or page interaction:", error);
        await browser.close();
        throw error;
    }
}
async function main() {
    try {
        console.log("Logging into Bluesky...");
        // Login to Bluesky
        await agent.login({
            identifier: process.env.BLUESKY_USERNAME,
            password: process.env.BLUESKY_PASSWORD,
        });
        console.log("Logged into Bluesky successfully.");
        // Load the last three tweet hashes from file
        let lastTweetIds = loadLastTweetHashes();
        setInterval(async () => {
            console.log("Starting new interval to check for latest tweets...");
            try {
                const tweets = await scrapeLatestTweets(process.env.TWITTER_PROFILE);
                for (const tweet of tweets) {
                    if (!lastTweetIds.includes(tweet.id)) {
                        // Start with the tweet text
                        let postContent = `${tweet.text}`;
                        // If the tweet contains images, append them to the post
                        if (tweet.images.length > 0) {
                            postContent += `\n\n(attached: ${tweet.images.join(", ")})`;
                        }
                        // Add two new lines and the "mirrored from X" text at the bottom
                        postContent += `\n\n(mirrored from X)`;
                        console.log(`New tweet found. Tweet ID: "${tweet.id}". Posting to Bluesky...`);
                        try {
                            // Correct the post format for Bluesky
                            await agent.post({
                                $type: "app.bsky.feed.post", // Specify the type explicitly
                                text: postContent, // Ensure text is correctly passed with the added content
                            });
                            console.log(`Successfully posted tweet to Bluesky: "${postContent}"`);
                            // Update the last posted tweet IDs
                            lastTweetIds.push(tweet.id);
                            if (lastTweetIds.length > 3) {
                                // Keep only the latest three tweet IDs to avoid storing too many
                                lastTweetIds = lastTweetIds.slice(-3);
                            }
                            console.log(`Updated lastTweetIds to: "${lastTweetIds}"`);
                            // Save the last tweet IDs to the file
                            saveLastTweetHashes(lastTweetIds);
                        }
                        catch (error) {
                            console.error("Error while posting to Bluesky:", error);
                        }
                    }
                    else {
                        console.log(`Tweet with ID "${tweet.id}" has already been posted. Skipping.`);
                    }
                }
            }
            catch (error) {
                console.error("Error fetching or posting tweets:", error);
            }
        }, IntervalTime);
    }
    catch (error) {
        console.error("Error logging into Bluesky:", error);
    }
}
main();
