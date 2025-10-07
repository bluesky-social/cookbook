// Learn more https://docs.expo.io/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config')

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname)

// Allows accessing /assets/oauth-client-metadata.json when running "expo start --web"
config.resolver.assetExts.push('json')

module.exports = config
