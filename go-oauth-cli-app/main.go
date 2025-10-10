package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"

	"github.com/bluesky-social/indigo/atproto/auth/oauth"
	"github.com/urfave/cli/v3"
)

// returns immediately, returning the now-listening port number.
// When the callback endpoint is requested, it returns the query parameters to the passed channel, and then shuts itself down
func listenForCallback(ctx context.Context, res chan url.Values) (int, error) {
	listener, err := net.Listen("tcp", ":0") // next available port
	if err != nil {
		return 0, err
	}

	mux := http.NewServeMux()
	server := &http.Server{
		Handler: mux,
	}

	mux.HandleFunc("/callback", func(w http.ResponseWriter, r *http.Request) {
		res <- r.URL.Query()
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(200)
		w.Write([]byte("<!DOCTYPE html><html><body onload='close();'>OK</body></html>\n")) // close the webpage
		go server.Shutdown(ctx)
	})

	go func() {
		err := server.Serve(listener)
		if !errors.Is(err, http.ErrServerClosed) {
			panic(err)
		}
	}()

	return listener.Addr().(*net.TCPAddr).Port, nil
}

func main() {
	config := oauth.ClientConfig{
		ClientID:  "https://retr0.id/stuff/go-oauth-cli-app.json",
		Scopes:    []string{"atproto", "repo:app.bsky.feed.post?action=create"},
		UserAgent: "go-oauth-cli-app example",
	}

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

					callbackRes := make(chan url.Values, 1)
					listenPort, err := listenForCallback(ctx, callbackRes)
					if err != nil {
						return err
					}

					fmt.Println("listening on", listenPort)
					config.CallbackURL = fmt.Sprintf("http://127.0.0.1:%d/callback", listenPort)

					oauthClient := oauth.NewClientApp(&config, oauth.NewMemStore()) // TODO: sqlite store in ~/.config/ or similar
					authUrl, err := oauthClient.StartAuthFlow(ctx, identifier)
					if err != nil {
						return fmt.Errorf("logging in: %w", err)
					}
					fmt.Printf("authUrl: %s\n", authUrl)

					session, err := oauthClient.ProcessCallback(ctx, <-callbackRes)
					if err != nil {
						return err
					}

					fmt.Println("logged in:", session.AccountDID)

					return nil
				},
			},
		},
	}

	if err := cmd.Run(context.Background(), os.Args); err != nil {
		log.Fatal(err)
	}
}
