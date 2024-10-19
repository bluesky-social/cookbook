import { BskyAgent } from "@atproto/api";
import * as dotenv from "dotenv";
import * as process from "process";
import * as puppeteer from "puppeteer";
import * as fs from "fs";
import * as path from "path";
import crypto from "crypto"; // for generating unique hashes

dotenv.config();

const COOKIES_PATH = path.join(__dirname, "cookies.json");
const HASHES_PATH = path.join(__dirname, "lastTweetHashes.json");
const IntervalTime = 1000 * 60; //* 5; // 5 minutes
const HASH_LOG_SIZE = 10;

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

// Function to load the last three tweet hashes from a file
function loadLastTweetHashes(): string[] {
    if (fs.existsSync(HASHES_PATH)) {
        return JSON.parse(fs.readFileSync(HASHES_PATH, "utf8"));
    }
    return [];
}

// Function to save the last three tweet hashes to a file
function saveLastTweetHashes(hashes: string[]) {
    fs.writeFileSync(HASHES_PATH, JSON.stringify(hashes, null, 2));
    console.log("Last tweet hashes saved to file.");
}

// Function to scrape the latest three tweets and handle quote tweets and image URLs properly
async function scrapeLatestTweets(username: string) {
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
            const tweetElements = Array.from(
                document.querySelectorAll("article"),
            );

            return tweetElements.slice(0, 3).map((el) => {
                // Main tweet text
                const mainTweetText =
                    el.querySelector("div[data-testid='tweetText']")
                        ?.textContent || "";

                // Check if the tweet contains a quoted tweet (look for nested div with data-testid='tweetText')
                let quotedTweetText = "";
                const quoteElement = el.querySelector(
                    "div[aria-labelledby] div[data-testid='tweetText']",
                );

                if (
                    quoteElement &&
                    quoteElement.textContent !== mainTweetText
                ) {
                    quotedTweetText = `\n\nQuoted tweet: "${quoteElement.textContent}"`;
                }

                // Initialize arrays for image and video URLs
                let imageUrls: string[] = [];
                let videoUrls: string[] = [];

                // Select image elements and cast to HTMLImageElement to access 'src'
                const imageElements = el.querySelectorAll(
                    'img[alt="Image"]',
                ) as NodeListOf<HTMLImageElement>;
                if (imageElements.length > 0) {
                    imageUrls = Array.from(imageElements).map((img) => img.src); // Get the src attribute of each image
                }

                // Select video source elements and get the src attribute
                const videoElements = el.querySelectorAll(
                    'source[type="video/mp4"]',
                ) as NodeListOf<HTMLSourceElement>;
                if (videoElements.length > 0) {
                    videoUrls = Array.from(videoElements).map(
                        (video) => video.src,
                    ); // Get the src attribute of each video
                }

                // Return the combined main tweet text, quoted tweet text (if any), image URLs, and video URLs
                return {
                    text: mainTweetText.trim() + quotedTweetText,
                    images: imageUrls, // Attach the array of image URLs
                    videos: videoUrls, // Attach the array of video URLs
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
            id: crypto.createHash("sha256").update(tweet.text).digest("hex"),
            text: tweet.text,
            images: tweet.images, // Include the image URLs in the tweet data
        }));

        return tweetData;
    } catch (error) {
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
            identifier: process.env.BLUESKY_USERNAME!,
            password: process.env.BLUESKY_PASSWORD!,
        });
        console.log("Logged into Bluesky successfully.");

        // Load the last three tweet hashes from file
        let lastTweetIds = loadLastTweetHashes();

        setInterval(async () => {
            console.log("Starting new interval to check for latest tweets...");
            try {
                const tweets = await scrapeLatestTweets(
                    process.env.TWITTER_PROFILE!,
                );

                for (const tweet of tweets) {
                    // Check if the tweet ID (hash) already exists in the lastTweetIds
                    if (!lastTweetIds.some((id) => id === tweet.id)) {
                        // New tweet detected, proceed to post it to Bluesky
                        const postContent = `${tweet.text}\n\n(mirrored from X)`;
                        console.log(
                            `New tweet found. Tweet ID: "${tweet.id}". Posting to Bluesky...`,
                        );

                        try {
                            // Post the tweet to Bluesky
                            await agent.post({
                                $type: "app.bsky.feed.post", // Specify the type explicitly
                                text: postContent, // Ensure text is correctly passed with the added content
                            });
                            console.log(
                                `Successfully posted tweet to Bluesky: "${postContent}"`,
                            );

                            // Add the newly posted tweet's hash to the lastTweetIds array
                            lastTweetIds.push(tweet.id);

                            // Keep only the latest HASH_LOG_SIZE tweet IDs to avoid storing too many
                            if (lastTweetIds.length > HASH_LOG_SIZE) {
                                lastTweetIds =
                                    lastTweetIds.slice(-HASH_LOG_SIZE);
                            }

                            // Save the updated last tweet hashes to the file
                            saveLastTweetHashes(lastTweetIds);
                            console.log(
                                `Updated lastTweetIds to: "${lastTweetIds}"`,
                            );
                        } catch (error) {
                            console.error(
                                "Error while posting to Bluesky:",
                                error,
                            );
                        }
                    } else {
                        console.log(
                            `Tweet with ID "${tweet.id}" has already been posted. Skipping.`,
                        );
                    }
                }
            } catch (error) {
                console.error("Error fetching or posting tweets:", error);
            }
        }, IntervalTime);
    } catch (error) {
        console.error("Error logging into Bluesky:", error);
    }
}

main();
