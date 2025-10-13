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
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/adrg/xdg"
	"github.com/bluesky-social/indigo/atproto/auth/oauth"
	"github.com/bluesky-social/indigo/atproto/syntax"
	"github.com/urfave/cli/v3"
)

// listens in the background and immediately returns the now-listening port number.
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
		// enough HTML to immediately close the webpage
		w.Write([]byte("<!DOCTYPE html><html><body onload='close();'>OK</body></html>\n"))
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

// Follows XDG conventions and creates the directories if necessary.
// By default, on linux, this will be "~/.local/share/go-oauth-cli-app/oauth_sessions.sqlite3"
func prepareDbPath() (string, error) {
	appDataDir := filepath.Join(xdg.DataHome, "go-oauth-cli-app")

	if err := os.MkdirAll(appDataDir, 0o700); err != nil {
		return "", fmt.Errorf("failed to create app data directory: %w", err)
	}

	return filepath.Join(appDataDir, "oauth_sessions.sqlite3"), nil
}

func buildOAuthClient() (*oauth.ClientConfig, *oauth.ClientApp, *SqliteStore, error) {
	config := oauth.ClientConfig{
		ClientID:  "https://retr0.id/stuff/go-oauth-cli-app.json",
		Scopes:    []string{"atproto", "repo:app.bsky.feed.post?action=create"},
		UserAgent: "go-oauth-cli-app example",
	}

	dbPath, err := prepareDbPath()
	if err != nil {
		return nil, nil, nil, err
	}

	store, err := NewSqliteStore(&SqliteStoreConfig{
		DatabasePath:              dbPath,
		SessionExpiryDuration:     time.Hour * 24 * 90,
		SessionInactivityDuration: time.Hour * 24 * 14,
		AuthRequestExpiryDuration: time.Minute * 30,
	})
	if err != nil {
		return nil, nil, nil, err
	}

	oauthClient := oauth.NewClientApp(&config, store)

	return &config, oauthClient, store, nil
}

func main() {

	cmd := &cli.Command{
		Usage: "A basic example CLI OAuth client using the indigo SDK",
		Commands: []*cli.Command{
			{
				Name:  "login",
				Usage: "log in to an atproto account (by handle, DID, or Authorization server)",
				Action: func(ctx context.Context, cmd *cli.Command) error {
					identifier := cmd.Args().First()
					if identifier == "" {
						return fmt.Errorf("identifier required")
					}

					config, oauthClient, _, err := buildOAuthClient()
					if err != nil {
						return err
					}

					callbackRes := make(chan url.Values, 1)
					listenPort, err := listenForCallback(ctx, callbackRes)
					if err != nil {
						return err
					}

					fmt.Println("listening on", listenPort)
					config.CallbackURL = fmt.Sprintf("http://127.0.0.1:%d/callback", listenPort)

					authUrl, err := oauthClient.StartAuthFlow(ctx, identifier)
					if err != nil {
						return fmt.Errorf("logging in: %w", err)
					}
					fmt.Printf("Navigating to: %s\n", authUrl)

					// Note: StartAuthFlow should internally guarantee this anyway, but since we're passing it to xdg-open we want
					// to be especially certain.
					if !strings.HasPrefix(authUrl, "https://") {
						panic("non-https authUrl")
					}
					if err := exec.Command("xdg-open", authUrl).Run(); err != nil {
						fmt.Println("Failed to open browser automatically. Please manually visit the above link.")
					}

					session, err := oauthClient.ProcessCallback(ctx, <-callbackRes)
					if err != nil {
						return err
					}

					fmt.Println("logged in:", session.AccountDID)

					return nil
				},
			},
			{
				Name:  "status",
				Usage: "print information about the current OAuth session, if one exists",
				Action: func(ctx context.Context, cmd *cli.Command) error {
					_, oauthClient, store, err := buildOAuthClient()
					if err != nil {
						return err
					}

					lastSessData, err := store.GetMostRecentSession(ctx)
					if err != nil {
						return err
					}

					oauthSess, err := oauthClient.ResumeSession(ctx, lastSessData.AccountDID, lastSessData.SessionID)
					if err != nil {
						return err
					}

					c := oauthSess.APIClient()
					var resp struct {
						Handle string `json:"handle"`
					}
					if err := c.Get(ctx, "com.atproto.server.getSession", nil, &resp); err != nil {
						return err
					}

					fmt.Println("did:   ", oauthSess.Data.AccountDID)
					fmt.Println("handle:", resp.Handle)
					fmt.Println("host:  ", oauthSess.Data.HostURL)

					return nil
				},
			},
			{
				Name:  "bsky-post",
				Usage: "post a message to bsky",
				Action: func(ctx context.Context, cmd *cli.Command) error {
					msg := cmd.Args().First()
					if msg == "" {
						return fmt.Errorf("message text required")
					}

					_, oauthClient, store, err := buildOAuthClient()
					if err != nil {
						return err
					}

					lastSessData, err := store.GetMostRecentSession(ctx)
					if err != nil {
						return err
					}

					oauthSess, err := oauthClient.ResumeSession(ctx, lastSessData.AccountDID, lastSessData.SessionID)
					if err != nil {
						return err
					}

					c := oauthSess.APIClient()

					body := map[string]any{
						"repo":       c.AccountDID.String(),
						"collection": "app.bsky.feed.post",
						"record": map[string]any{
							"$type":     "app.bsky.feed.post",
							"text":      msg,
							"createdAt": syntax.DatetimeNow(),
						},
					}
					var resp struct {
						Uri syntax.ATURI `json:"uri"`
					}

					fmt.Println("posting...")
					if err := c.Post(ctx, "com.atproto.repo.createRecord", body, &resp); err != nil {
						return err
					}

					fmt.Printf("Success! Your post should be live at https://bsky.app/profile/%s/post/%s\n", resp.Uri.Authority(), resp.Uri.RecordKey())
					return nil
				},
			},
		},
	}

	if err := cmd.Run(context.Background(), os.Args); err != nil {
		log.Fatal(err)
	}
}
