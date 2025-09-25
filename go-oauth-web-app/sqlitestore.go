package main

import (
	"context"

	"github.com/bluesky-social/indigo/atproto/auth/oauth"
	"github.com/bluesky-social/indigo/atproto/syntax"
)

// Implements the [oauth.ClientAuthStore] interface
type SqliteStore struct {
}

var _ oauth.ClientAuthStore = &SqliteStore{}

func NewSqliteStore() *SqliteStore {
	return &SqliteStore{}
}

func (m *SqliteStore) GetSession(ctx context.Context, did syntax.DID, sessionID string) (*oauth.ClientSessionData, error) {
	return nil, nil
}

func (m *SqliteStore) SaveSession(ctx context.Context, sess oauth.ClientSessionData) error {
	return nil
}

func (m *SqliteStore) DeleteSession(ctx context.Context, did syntax.DID, sessionID string) error {
	return nil
}

func (m *SqliteStore) GetAuthRequestInfo(ctx context.Context, state string) (*oauth.AuthRequestData, error) {
	return nil, nil
}

func (m *SqliteStore) SaveAuthRequestInfo(ctx context.Context, info oauth.AuthRequestData) error {
	return nil
}

func (m *SqliteStore) DeleteAuthRequestInfo(ctx context.Context, state string) error {
	return nil
}
