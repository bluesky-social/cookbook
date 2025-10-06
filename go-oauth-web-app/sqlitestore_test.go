package main

import (
	"testing"
	"time"

	"github.com/bluesky-social/indigo/atproto/auth/oauth"
)

func TestSession(t *testing.T) {
	store, err := NewSqliteStore(&SqliteStoreConfig{
		DatabasePath:              "file::memory:",
		SessionExpiryDuration:     time.Hour * 24 * 90,
		SessionInactivityDuration: time.Hour * 24 * 14,
		AuthRequestExpiryDuration: time.Minute * 30,
	})
	if err != nil {
		t.Errorf("NewSqliteStore: %s", err)
	}
	err = store.SaveSession(t.Context(), oauth.ClientSessionData{
		AccountDID:  "did:web:bob.test",
		SessionID:   "sessionid123123",
		AccessToken: "test123",
	})
	if err != nil {
		t.Errorf("store.SaveSession: %s", err)
	}

	res, err := store.GetSession(t.Context(), "did:web:bob.test", "sessionid123123")
	if err != nil {
		t.Errorf("store.GetSession: %s", err)
	}

	if res.AccessToken != "test123" {
		t.Error("retrieved session token did not match")
	}

	err = store.DeleteSession(t.Context(), "did:web:bob.test", "sessionid123123")
	if err != nil {
		t.Errorf("store.DeleteSession: %s", err)
	}

	_, err = store.GetSession(t.Context(), "did:web:bob.test", "sessionid123123")
	if err == nil {
		t.Errorf("expected retrieval of deleted session to fail, but it did not")
	}
}

func TestAuthRequest(t *testing.T) {
	store, err := NewSqliteStore(&SqliteStoreConfig{
		DatabasePath:              "file::memory:",
		SessionExpiryDuration:     time.Hour * 24 * 90,
		SessionInactivityDuration: time.Hour * 24 * 14,
		AuthRequestExpiryDuration: time.Minute * 30,
	})
	if err != nil {
		t.Errorf("NewSqliteStore: %s", err)
	}
	err = store.SaveAuthRequestInfo(t.Context(), oauth.AuthRequestData{
		State:         "state123",
		AuthServerURL: "example.com",
	})
	if err != nil {
		t.Errorf("store.SaveAuthRequestInfo: %s", err)
	}

	res, err := store.GetAuthRequestInfo(t.Context(), "state123")
	if err != nil {
		t.Errorf("store.GetAuthRequestInfo: %s", err)
	}

	if res.AuthServerURL != "example.com" {
		t.Error("retrieved AuthServerURL token did not match")
	}

	err = store.DeleteAuthRequestInfo(t.Context(), "state123")
	if err != nil {
		t.Errorf("store.DeleteAuthRequestInfo: %s", err)
	}

	_, err = store.GetAuthRequestInfo(t.Context(), "state123")
	if err == nil {
		t.Error("expected retrieval of deleted auth request to fail, but it did not")
	}
}
