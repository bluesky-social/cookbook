package main

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"html/template"
	"log/slog"
	"net/http"
	"os"
	"time"

	_ "github.com/joho/godotenv/autoload"

	"github.com/bluesky-social/indigo/atproto/auth/oauth"
	"github.com/bluesky-social/indigo/atproto/crypto"
	"github.com/bluesky-social/indigo/atproto/identity"
	"github.com/bluesky-social/indigo/atproto/syntax"

	"github.com/gorilla/sessions"
	"github.com/urfave/cli/v2"
)

func main() {
	app := cli.App{
		Name:   "oauth-web-demo",
		Usage:  "atproto OAuth web server demo",
		Action: runServer,
		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:     "session-secret",
				Usage:    "random string/token used for session cookie security",
				Required: true,
				EnvVars:  []string{"SESSION_SECRET"},
			},
			&cli.StringFlag{
				Name:    "hostname",
				Usage:   "public host name for this client (if not localhost dev mode)",
				EnvVars: []string{"CLIENT_HOSTNAME"},
			},
			&cli.StringFlag{
				Name:    "client-secret-key",
				Usage:   "confidential client secret key. should be P-256 private key in multibase encoding",
				EnvVars: []string{"CLIENT_SECRET_KEY"},
			},
			&cli.StringFlag{
				Name:    "client-secret-key-id",
				Usage:   "key id for client-secret-key",
				Value:   "primary",
				EnvVars: []string{"CLIENT_SECRET_KEY_ID"},
			},
		},
	}
	h := slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelDebug})
	slog.SetDefault(slog.New(h))
	app.RunAndExitOnError()
}

type Server struct {
	CookieStore *sessions.CookieStore
	Dir         identity.Directory
	OAuth       *oauth.ClientApp
}

type TmplData struct {
	DID    *syntax.DID
	Handle string
	Error  string
}

type SuccessTmplData struct {
	DID    *syntax.DID
	Handle string
	PdsUrl string
	Repo   string
	Rkey   string
	AtUri  string
}

//go:embed "base.html"
var tmplBaseText string

//go:embed "home.html"
var tmplHomeText string
var tmplHome = template.Must(template.Must(template.New("home.html").Parse(tmplBaseText)).Parse(tmplHomeText))

//go:embed "login.html"
var tmplLoginText string
var tmplLogin = template.Must(template.Must(template.New("login.html").Parse(tmplBaseText)).Parse(tmplLoginText))

//go:embed "post.html"
var tmplPostText string
var tmplPost = template.Must(template.Must(template.New("post.html").Parse(tmplBaseText)).Parse(tmplPostText))

//go:embed "post_success.html"
var tmplPostSuccessText string
var tmplPostSuccess = template.Must(template.Must(template.New("post_success.html").Parse(tmplBaseText)).Parse(tmplPostSuccessText))

//go:embed "error.html"
var tmplErrorText string
var tmplError = template.Must(template.Must(template.New("error.html").Parse(tmplBaseText)).Parse(tmplErrorText))

func runServer(cctx *cli.Context) error {

	scopes := []string{"atproto", "repo:app.bsky.feed.post?action=create"}
	bind := ":8080"

	var config oauth.ClientConfig
	hostname := cctx.String("hostname")
	if hostname == "" {
		config = oauth.NewLocalhostConfig(
			fmt.Sprintf("http://127.0.0.1%s/oauth/callback", bind),
			scopes,
		)
		slog.Info("configuring localhost OAuth client", "CallbackURL", config.CallbackURL)
	} else {
		config = oauth.NewPublicConfig(
			fmt.Sprintf("https://%s/oauth-client-metadata.json", hostname),
			fmt.Sprintf("https://%s/oauth/callback", hostname),
			scopes,
		)
	}

	// If a client secret key is provided (as a multibase string), turn this in to a confidential client
	if cctx.String("client-secret-key") != "" && hostname != "" {
		priv, err := crypto.ParsePrivateMultibase(cctx.String("client-secret-key"))
		if err != nil {
			return err
		}
		if err := config.SetClientSecret(priv, cctx.String("client-secret-key-id")); err != nil {
			return err
		}
		slog.Info("configuring confidential OAuth client")
	}

	store, err := NewSqliteStore(&SqliteStoreConfig{
		DatabasePath:              "oauth_sessions.sqlite3",
		SessionExpiryDuration:     time.Hour * 24 * 90,
		SessionInactivityDuration: time.Hour * 24 * 14,
		AuthRequestExpiryDuration: time.Minute * 30,
	})
	if err != nil {
		return err
	}
	oauthClient := oauth.NewClientApp(&config, store)

	srv := Server{
		CookieStore: sessions.NewCookieStore([]byte(cctx.String("session-secret"))),
		Dir:         identity.DefaultDirectory(),
		OAuth:       oauthClient,
	}

	http.HandleFunc("GET /", srv.Homepage)
	http.HandleFunc("GET /oauth-client-metadata.json", srv.ClientMetadata)
	http.HandleFunc("GET /oauth/jwks.json", srv.JWKS)
	http.HandleFunc("GET /oauth/login", srv.OAuthLogin)
	http.HandleFunc("POST /oauth/login", srv.OAuthLogin)
	http.HandleFunc("GET /oauth/callback", srv.OAuthCallback)
	http.HandleFunc("GET /oauth/logout", srv.OAuthLogout)
	http.HandleFunc("GET /bsky/post", srv.Post)
	http.HandleFunc("POST /bsky/post", srv.Post)

	slog.Info("starting http server", "bind", bind)
	if err := http.ListenAndServe(bind, nil); err != nil {
		slog.Error("http shutdown", "err", err)
	}
	return nil
}

func (s *Server) currentSessionDID(r *http.Request) (*syntax.DID, string, string) {
	sess, _ := s.CookieStore.Get(r, "oauth-demo")
	accountDID, ok := sess.Values["account_did"].(string)
	if !ok || accountDID == "" {
		return nil, "", ""
	}
	did, err := syntax.ParseDID(accountDID)
	if err != nil {
		return nil, "", ""
	}
	sessionID, ok := sess.Values["session_id"].(string)
	if !ok || sessionID == "" {
		return nil, "", ""
	}
	handle, ok := sess.Values["handle"].(string)
	if !ok || handle == "" {
		return nil, "", ""
	}

	return &did, sessionID, handle
}

func strPtr(raw string) *string {
	return &raw
}

func (s *Server) ClientMetadata(w http.ResponseWriter, r *http.Request) {
	slog.Info("client metadata request", "url", r.URL, "host", r.Host)

	meta := s.OAuth.Config.ClientMetadata()
	if s.OAuth.Config.IsConfidential() {
		meta.JWKSURI = strPtr(fmt.Sprintf("https://%s/oauth/jwks.json", r.Host))
	}
	meta.ClientName = strPtr("indigo atp-oauth-demo")
	meta.ClientURI = strPtr(fmt.Sprintf("https://%s", r.Host))

	// internal consistency check
	if err := meta.Validate(s.OAuth.Config.ClientID); err != nil {
		slog.Error("validating client metadata", "err", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(meta); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func (s *Server) JWKS(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	body := s.OAuth.Config.PublicJWKS()
	if err := json.NewEncoder(w).Encode(body); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func (s *Server) Homepage(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// attempts to load Session to display links
	did, sessionID, handle := s.currentSessionDID(r)
	if did == nil {
		tmplHome.Execute(w, nil)
		return
	}

	_, err := s.OAuth.ResumeSession(ctx, *did, sessionID)
	if err != nil {
		tmplHome.Execute(w, nil)
		return
	}
	tmplHome.Execute(w, TmplData{DID: did, Handle: handle})
}

func (s *Server) OAuthLogin(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	if r.Method != "POST" {
		tmplLogin.Execute(w, nil)
		return
	}

	if err := r.ParseForm(); err != nil {
		http.Error(w, fmt.Errorf("parsing form data: %w", err).Error(), http.StatusBadRequest)
		return
	}

	username := r.PostFormValue("username")

	slog.Info("OAuthLogin", "client_id", s.OAuth.Config.ClientID, "callback_url", s.OAuth.Config.CallbackURL)

	redirectURL, err := s.OAuth.StartAuthFlow(ctx, username)
	if err != nil {
		var oauthErr = fmt.Errorf("OAuth login failed: %w", err).Error()
		slog.Error(oauthErr)
		tmplLogin.Execute(w, TmplData{Error: oauthErr})
		return
	}

	http.Redirect(w, r, redirectURL, http.StatusFound)
}

func (s *Server) OAuthCallback(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	params := r.URL.Query()
	slog.Info("received callback", "params", params)

	sessData, err := s.OAuth.ProcessCallback(ctx, r.URL.Query())
	if err != nil {
		var callbackErr = fmt.Errorf("failed processing oauth callback: %w", err).Error()
		slog.Error(callbackErr)
		tmplError.Execute(w, TmplData{Error: callbackErr})
		return
	}

	// retrieve session metadata
	oauthSess, err := s.OAuth.ResumeSession(ctx, sessData.AccountDID, sessData.SessionID)
	if err != nil {
		http.Error(w, "not authenticated", http.StatusUnauthorized)
		return
	}
	c := oauthSess.APIClient()
	var resp struct {
		Handle string `json:"handle"`
		// TODO: more fields?
	}
	if err := c.Get(ctx, "com.atproto.server.getSession", nil, &resp); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// create signed cookie session, indicating account DID
	sess, _ := s.CookieStore.Get(r, "oauth-demo")
	sess.Values["account_did"] = sessData.AccountDID.String()
	sess.Values["session_id"] = sessData.SessionID
	sess.Values["handle"] = resp.Handle
	if err := sess.Save(r, w); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	slog.Info("login successful", "did", sessData.AccountDID.String())
	http.Redirect(w, r, "/bsky/post", http.StatusFound)
}

func (s *Server) OAuthLogout(w http.ResponseWriter, r *http.Request) {

	// revoke tokens and delete session from auth store
	did, sessionID, _ := s.currentSessionDID(r)
	if did != nil {
		if err := s.OAuth.Logout(r.Context(), *did, sessionID); err != nil {
			slog.Error("failed to delete session", "did", did, "err", err)
		}
	}

	// wipe all secure cookie session data
	sess, _ := s.CookieStore.Get(r, "oauth-demo")
	sess.Values = make(map[any]any)
	err := sess.Save(r, w)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	slog.Info("logged out")
	http.Redirect(w, r, "/", http.StatusFound)
}

func (s *Server) Post(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	slog.Info("in post handler")

	did, sessionID, handle := s.currentSessionDID(r)
	if did == nil {
		// TODO: supposed to set a WWW header; and could redirect?
		http.Error(w, "not authenticated", http.StatusUnauthorized)
		return
	}

	if r.Method != "POST" {
		tmplPost.Execute(w, TmplData{DID: did, Handle: handle})
		return
	}

	oauthSess, err := s.OAuth.ResumeSession(ctx, *did, sessionID)
	if err != nil {
		http.Error(w, "not authenticated", http.StatusUnauthorized)
		return
	}
	c := oauthSess.APIClient()

	if err := r.ParseForm(); err != nil {
		http.Error(w, fmt.Errorf("parsing form data: %w", err).Error(), http.StatusBadRequest)
		return
	}
	text := r.PostFormValue("post_text")

	// TODO: facet parsing

	body := map[string]any{
		"repo":       c.AccountDID.String(),
		"collection": "app.bsky.feed.post",
		"record": map[string]any{
			"$type":     "app.bsky.feed.post",
			"text":      text,
			"facets":    parseFacets(text),
			"createdAt": syntax.DatetimeNow(),
		},
	}
	var resp struct {
		Uri syntax.ATURI `json:"uri"` // the only field we care about
	}

	slog.Info("attempting post...", "text", text)
	if err := c.Post(ctx, "com.atproto.repo.createRecord", body, &resp); err != nil {
		postErr := fmt.Errorf("posting failed: %w", err).Error()
		slog.Error(postErr)
		tmplError.Execute(w, TmplData{DID: did, Handle: handle, Error: postErr})
		return
	}

	tmplPostSuccess.Execute(w, SuccessTmplData{
		DID:    did,
		Handle: handle,
		PdsUrl: oauthSess.Data.HostURL,
		Repo:   resp.Uri.Authority().String(),
		Rkey:   resp.Uri.RecordKey().String(),
		AtUri:  resp.Uri.String(),
	})
}
