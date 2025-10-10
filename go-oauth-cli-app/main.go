package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/bluesky-social/indigo/atproto/auth/oauth"

	"github.com/urfave/cli/v3"
)

func main() {
	cmd := &cli.Command{
		Commands: []*cli.Command{
			{
				Name:  "login",
				Usage: "log in to an atproto account (by handle, DID, or Authorization server)",
				Action: func(ctx context.Context, cmd *cli.Command) error {
					identifier := cmd.Args().First()
					if identifier == "" {
						return fmt.Errorf("identifier required")
					}
					config := oauth.ClientConfig{
						ClientID:    "https://retr0.id/stuff/go-oauth-cli-app.json",
						CallbackURL: "http://127.0.0.1:1337/callback", // TODO: set something up here!!!
						Scopes:      []string{"atproto", "repo:app.bsky.feed.post?action=create"},
					}
					oauthClient := oauth.NewClientApp(&config, oauth.NewMemStore())
					authUrl, err := oauthClient.StartAuthFlow(ctx, identifier)
					if err != nil {
						return fmt.Errorf("logging in: %w", err)
					}
					fmt.Printf("authUrl: %s\n", authUrl)
					return nil
				},
			},
		},
	}

	if err := cmd.Run(context.Background(), os.Args); err != nil {
		log.Fatal(err)
	}
}
