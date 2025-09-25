package main

import (
	"context"
	"time"

	"github.com/bluesky-social/indigo/atproto/auth/oauth"
	"github.com/bluesky-social/indigo/atproto/syntax"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// Implements the [oauth.ClientAuthStore] interface, backed by sqlite via gorm
//
// gorm might be overkill here, but it means it's easy to port this to a different db backend
type SqliteStore struct {
	db *gorm.DB
	// all operations involve a single query, and gorm itself is thread-safe, so no need for a lock
}

var _ oauth.ClientAuthStore = &SqliteStore{}

type storedSessionData struct {
	AccountDid syntax.DID              `gorm:"primaryKey"`
	SessionID  string                  `gorm:"primaryKey"`
	Data       oauth.ClientSessionData `gorm:"serializer:json"`
	CreatedAt  time.Time
	UpdatedAt  time.Time
}

type storedAuthRequest struct {
	State     string                `gorm:"primaryKey"`
	Data      oauth.AuthRequestData `gorm:"serializer:json"`
	CreatedAt time.Time
	UpdatedAt time.Time
}

func NewSqliteStore(path string) *SqliteStore {
	db, err := gorm.Open(sqlite.Open(path), &gorm.Config{})
	if err != nil {
		panic("failed to connect database")
	}

	db.AutoMigrate(&storedSessionData{})
	db.AutoMigrate(&storedAuthRequest{})

	return &SqliteStore{db}
}

func (m *SqliteStore) GetSession(ctx context.Context, did syntax.DID, sessionID string) (*oauth.ClientSessionData, error) {
	var row storedSessionData
	res := m.db.WithContext(ctx).Where(&storedSessionData{
		AccountDid: did,
		SessionID:  sessionID,
	}).First(&row)
	if res.Error != nil {
		return nil, res.Error
	}
	return &row.Data, nil
}

func (m *SqliteStore) SaveSession(ctx context.Context, sess oauth.ClientSessionData) error {
	// upsert
	res := m.db.WithContext(ctx).Clauses(clause.OnConflict{
		UpdateAll: true,
	}).Create(&storedSessionData{
		AccountDid: sess.AccountDID,
		SessionID:  sess.SessionID,
		Data:       sess,
	})
	return res.Error
}

func (m *SqliteStore) DeleteSession(ctx context.Context, did syntax.DID, sessionID string) error {
	res := m.db.WithContext(ctx).Delete(&storedSessionData{
		AccountDid: did,
		SessionID:  sessionID,
	})
	return res.Error
}

func (m *SqliteStore) GetAuthRequestInfo(ctx context.Context, state string) (*oauth.AuthRequestData, error) {
	var row storedAuthRequest
	res := m.db.WithContext(ctx).Where(&storedAuthRequest{State: state}).First(&row)
	if res.Error != nil {
		return nil, res.Error
	}
	return &row.Data, nil
}

func (m *SqliteStore) SaveAuthRequestInfo(ctx context.Context, info oauth.AuthRequestData) error {
	// will fail if an auth request already exists for the same state
	res := m.db.WithContext(ctx).Create(&storedAuthRequest{
		State: info.State,
		Data:  info,
	})
	return res.Error
}

func (m *SqliteStore) DeleteAuthRequestInfo(ctx context.Context, state string) error {
	res := m.db.WithContext(ctx).Delete(&storedAuthRequest{State: state})
	return res.Error
}
