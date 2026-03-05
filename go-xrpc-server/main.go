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

var SERVICE_ID = "demo"

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

	// basic ASCII art homepage
	http.HandleFunc("GET /", HomeEndpoint)

	// did:web endpoint based on detected hostname
	http.HandleFunc("GET /.well-known/did.json", DidWebEndpoint)

	// public version of "echo" endpoint (auth is ignored)
	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echo", EchoEndpoint)

	// service-auth-optional version of "echo" endpoint. If auth header is provided, it must be valid. If it is not provided, request is still allowed.
	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echoAuthOptional", svcAuth.Middleware(EchoEndpoint, false))

	// service-auth-required version of "echo" endpoint
	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echoAuthRequired", svcAuth.Middleware(EchoEndpoint, true))

	// admin-only version of "echo" endpoint
	http.HandleFunc("POST /xrpc/dev.atbin.xrpc.echoAdmin", auth.AdminAuthMiddleware(EchoEndpoint, adminPasswords))

	slog.Info("starting http server", "bind", bind)
	if err := http.ListenAndServe(bind, nil); err != nil {
		slog.Error("http shutdown", "err", err)
	}
	return nil
}

type EchoRequestBody struct {
	Input string `json:"input"`
}

type EchoResponseBody struct {
	Output string `json:"output"`
	DID    string `json:"did,omitempty"`
}

func EchoEndpoint(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	// parse request body JSON
	var reqBody EchoRequestBody
	if err := json.NewDecoder(r.Body).Decode(&reqBody); err != nil {
		http.Error(w, fmt.Sprintf(`{"error": "BadRequest", "message": "%s"}`, err.Error()), http.StatusBadRequest)
		return
	}

	resBody := EchoResponseBody{
		Output: reqBody.Input,
	}

	// fetch authenticated DID from request context (if it was added by auth middleware)
	if did := r.Context().Value("did"); did != nil {
		resBody.DID = did.(syntax.DID).String()
	}

	if err := json.NewEncoder(w).Encode(resBody); err != nil {
		http.Error(w, fmt.Sprintf(`{"error": "InternalError", "message": "%s"}`, err.Error()), http.StatusBadRequest)
		return
	}
}

func DidWebEndpoint(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	doc := identity.DIDDocument{
		DID: syntax.DID(fmt.Sprintf("did:web:%s", r.Host)),
		Service: []identity.DocService{
			identity.DocService{
				ID:              "#" + SERVICE_ID,
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
