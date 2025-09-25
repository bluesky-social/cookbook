package main

import (
	"context"
	"fmt"
	"time"

	"github.com/bluesky-social/indigo/atproto/auth/oauth"
	"github.com/bluesky-social/indigo/atproto/syntax"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type SqliteStoreConfig struct {
	DatabasePath string

	// The purpose of these limits is to avoid dead sessions hanging around in the db indefinitely.
	// The durations here should be *at least as long as* the expected duration of the oauth session itself.
	SessionExpiryDuration     time.Duration // duration since session creation
	SessionInactivityDuration time.Duration // duration since last session update
	AuthRequestExpiryDuration time.Duration // duration since auth request creation
}

// Implements the [oauth.ClientAuthStore] interface, backed by sqlite via gorm
//
// gorm might be overkill here, but it means it's easy to port this to a different db backend
type SqliteStore struct {
	db  *gorm.DB
	cfg *SqliteStoreConfig
	// gorm itself is thread-safe, so no need for a lock
}

var _ oauth.ClientAuthStore = &SqliteStore{}

type storedSessionData struct {
	AccountDid syntax.DID              `gorm:"primaryKey"`
	SessionID  string                  `gorm:"primaryKey"`
	Data       oauth.ClientSessionData `gorm:"serializer:json"`
	CreatedAt  time.Time               `gorm:"index"`
	UpdatedAt  time.Time               `gorm:"index"`
}

type storedAuthRequest struct {
	State     string                `gorm:"primaryKey"`
	Data      oauth.AuthRequestData `gorm:"serializer:json"`
	CreatedAt time.Time             `gorm:"index"`
}

func NewSqliteStore(cfg *SqliteStoreConfig) (*SqliteStore, error) {
	if cfg == nil {
		return nil, fmt.Errorf("missing cfg")
	}
	if cfg.DatabasePath == "" {
		return nil, fmt.Errorf("missing DatabasePath")
	}
	if cfg.SessionExpiryDuration == 0 {
		return nil, fmt.Errorf("missing SessionExpiryDuration")
	}
	if cfg.SessionInactivityDuration == 0 {
		return nil, fmt.Errorf("missing SessionInactivityDuration")
	}
	if cfg.AuthRequestExpiryDuration == 0 {
		return nil, fmt.Errorf("missing AuthRequestExpiryDuration")
	}

	db, err := gorm.Open(sqlite.Open(cfg.DatabasePath), &gorm.Config{})
	if err != nil {
		return nil, fmt.Errorf("failed opening db: %w", err)
	}

	db.AutoMigrate(&storedSessionData{})
	db.AutoMigrate(&storedAuthRequest{})

	return &SqliteStore{db, cfg}, nil
}

func (m *SqliteStore) GetSession(ctx context.Context, did syntax.DID, sessionID string) (*oauth.ClientSessionData, error) {
	// bookkeeping: delete expired sessions
	expiry_threshold := time.Now().Add(-m.cfg.SessionExpiryDuration)
	inactive_threshold := time.Now().Add(-m.cfg.SessionInactivityDuration)
	m.db.WithContext(ctx).Where(
		"created_at < ? OR updated_at < ?", expiry_threshold, inactive_threshold,
	).Delete(&storedSessionData{})

	// finally, the query itself
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
	// bookkeeping: delete expired auth requests
	threshold := time.Now().Add(-m.cfg.AuthRequestExpiryDuration)
	m.db.WithContext(ctx).Where("created_at < ?", threshold).Delete(&storedAuthRequest{})

	// finally, the query itself
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
