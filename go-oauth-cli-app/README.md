# Go OAuth CLI App example

This example shows how to integrate ATProto OAuth login into a CLI app.

While it is possible to use a localhost client ID for testing (see `go-oauth-web-app`), this example uses a publicly hosted client metadata document at `https://retr0.id/stuff/go-oauth-cli-app.json` (the client ID). The advantage of using a non-localhost client ID is that users can more easily manage the permissions and sessions associated with the app, from their account settings. If you wish to modify this example (for example, changing the requested scopes), you'll need to host your own metadata document somewhere.

Completing the OAuth login process requires recieving the callback redirect. This is done by listening on localhost at a random available port.

## Installation

From this directory, run `go install`, which will build and install the binary at `~/go/bin/go-oauth-cli-app`.

Alternatively, you can run it directly via `go run .`

## Usage

Run the program with no arguments to see help text.

```
NAME:
   go-oauth-cli-app - A basic example CLI OAuth client using the indigo SDK

USAGE:
   go-oauth-cli-app [global options] [command [command options]]

COMMANDS:
   login      log in to an atproto account (by handle, DID, or Authorization server)
   status     print information about the current OAuth session, if one exists
   bsky-post  post a message to bsky
   help, h    Shows a list of commands or help for one command

GLOBAL OPTIONS:
   --help, -h  show help
```
