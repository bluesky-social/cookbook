package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	_ "github.com/joho/godotenv/autoload"

	"github.com/bluesky-social/indigo/atproto/auth"
	"github.com/bluesky-social/indigo/atproto/identity"
	"github.com/bluesky-social/indigo/atproto/syntax"

	"github.com/urfave/cli/v3"
)

func main() {
	app := cli.Command{
		Name:   "xrpc-server-demo",
		Usage:  "atproto XRPC HTTP API server demo",
		Action: runServer,
		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:    "service-did",
				Usage:   "DID for this service",
				Sources: cli.EnvVars("SERVICE_DID"),
			},
			&cli.StringFlag{
				Name:    "service-did-id",
				Usage:   "DID service ID (eg, fragment)",
				Value:   "demo",
				Sources: cli.EnvVars("SERVICE_DID_ID"),
			},
			&cli.StringSliceFlag{
				Name:    "admin-password",
				Value:   []string{"dummy123"},
				Usage:   "secret password/token for accessing admin endpoints (multiple values allowed)",
				Sources: cli.EnvVars("ADMIN_PASSWORD"),
			},
		},
	}
	h := slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelDebug})
	slog.SetDefault(slog.New(h))
	if err := app.Run(context.Background(), os.Args); err != nil {
		fmt.Println("%s", err)
	}
}

func runServer(ctx context.Context, cmd *cli.Command) error {

	bind := ":8080"
	serviceDID := cmd.String("service-did")
	adminPasswords := cmd.StringSlice("admin-password")
	dir := identity.DefaultDirectory()

	svcAuth := auth.ServiceAuthValidator{
		Audience:        serviceDID,
		Dir:             dir,
		TimestampLeeway: time.Second * 5,
	}

	http.HandleFunc("GET /", HomeEndpoint)

	// did:web endpoint
	http.HandleFunc("GET /.well-known/did.json", DidWebEndpoint)

	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echo", EchoEndpoint)
	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echoAuthOptional", svcAuth.Middleware(EchoEndpoint, false))
	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echoAuthRequired", svcAuth.Middleware(EchoEndpoint, true))
	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echoAdmin", auth.AdminAuthMiddleware(EchoEndpoint, adminPasswords))

	slog.Info("starting http server", "bind", bind)
	if err := http.ListenAndServe(bind, nil); err != nil {
		slog.Error("http shutdown", "err", err)
	}
	return nil
}

func HomeEndpoint(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.Write([]byte(`
___  ________________   ____             ______ ______________  __ ___________ 
\  \/  /\_  __ \____ \_/ ___\   ______  /  ___// __ \_  __ \  \/ // __ \_  __ \
 >    <  |  | \/  |_> >  \___  /_____/  \___ \\  ___/|  | \/\   /\  ___/|  | \/
/__/\_ \ |__|  |   __/ \___  >         /____  >\___  >__|    \_/  \___  >__|   
      \/       |__|        \/               \/     \/                 \/       

This is an AT Protocol demo server.

Most API routes are under /xrpc/

      Code: https://github.com/bluesky-social/cookbook
  Protocol: https://atproto.com
`))
}

func DidWebEndpoint(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	doc := identity.DIDDocument{
		DID: syntax.DID(fmt.Sprintf("did:web:%s", r.Host)),
		Service: []identity.DocService{
			identity.DocService{
				// TODO: passthrough config
				ID:              "#demo",
				Type:            "AtprotoExampleService",
				ServiceEndpoint: fmt.Sprintf("https://%s", r.Host),
			},
		},
	}
	if err := json.NewEncoder(w).Encode(doc); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

type EchoRequestBody struct {
	Input string `json:"input"`
}

type EchoResponseBody struct {
	Output string `json:"output"`
}

func EchoEndpoint(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var reqBody EchoRequestBody
	if err := json.NewDecoder(r.Body).Decode(&reqBody); err != nil {
		// XXX: error JSON body
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	resBody := EchoResponseBody{
		Output: reqBody.Input,
	}
	if err := json.NewEncoder(w).Encode(resBody); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}
