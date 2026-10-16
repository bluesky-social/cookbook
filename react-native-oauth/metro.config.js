// Learn more https://docs.expo.io/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config')

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname)

// Allows accessing /assets/oauth-client-metadata.json when running "expo start --web"
config.resolver.assetExts.push('json')

// @atproto/oauth-client-expo's dist is ESM that imports platform-split
// modules with explicit ".js" specifiers (e.g. `./expo-oauth-client.js`,
// shipped as `expo-oauth-client.web.js` / `expo-oauth-client.native.js`).
// Metro only applies platform extensions to extensionless specifiers, so
// resolve the literal path first (real .js files keep working) and fall back
// to the extensionless form, letting Metro pick the platform file.
const defaultResolveRequest = config.resolver.resolveRequest
config.resolver.resolveRequest = (context, moduleName, platform) => {
  const resolve = defaultResolveRequest ?? context.resolveRequest
  if (/^\.{1,2}\//.test(moduleName) && moduleName.endsWith('.js')) {
    try {
      return resolve(context, moduleName, platform)
    } catch {
      return resolve(context, moduleName.slice(0, -'.js'.length), platform)
    }
  }
  return resolve(context, moduleName, platform)
}

module.exports = config
