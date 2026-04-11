package cmd

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/compose"
	"github.com/Aureliolo/synthorg/cli/internal/config"
)

// TestBuildState_Postgres verifies that selecting the postgres persistence
// backend in init generates a random password, sets the default port, and
// persists both in the resulting State.
func TestBuildState_Postgres(t *testing.T) {
	a := setupAnswers{
		dir:                mustAbs(t, t.TempDir()),
		backendPortStr:     "3001",
		webPortStr:         "3000",
		sandbox:            false,
		dockerSock:         "",
		logLevel:           "info",
		persistenceBackend: "postgres",
		memoryBackend:      "mem0",
		busBackend:         "internal",
		postgresPort:       0,
	}

	state, err := buildState(a)
	if err != nil {
		t.Fatalf("buildState: %v", err)
	}

	if state.PersistenceBackend != "postgres" {
		t.Errorf("PersistenceBackend = %q, want postgres", state.PersistenceBackend)
	}
	if state.PostgresPort != 3002 {
		t.Errorf("PostgresPort = %d, want 3002 (default)", state.PostgresPort)
	}
	if len(state.PostgresPassword) < 32 {
		t.Errorf("PostgresPassword length = %d, want >= 32", len(state.PostgresPassword))
	}
}

// TestBuildState_PostgresCustomPort verifies --postgres-port is honoured.
func TestBuildState_PostgresCustomPort(t *testing.T) {
	a := setupAnswers{
		dir:                mustAbs(t, t.TempDir()),
		backendPortStr:     "3001",
		webPortStr:         "3000",
		sandbox:            false,
		dockerSock:         "",
		logLevel:           "info",
		persistenceBackend: "postgres",
		memoryBackend:      "mem0",
		busBackend:         "internal",
		postgresPort:       5433,
	}

	state, err := buildState(a)
	if err != nil {
		t.Fatalf("buildState: %v", err)
	}
	if state.PostgresPort != 5433 {
		t.Errorf("PostgresPort = %d, want 5433", state.PostgresPort)
	}
}

// TestBuildState_Sqlite verifies the default path still works for SQLite.
func TestBuildState_Sqlite(t *testing.T) {
	a := setupAnswers{
		dir:                mustAbs(t, t.TempDir()),
		backendPortStr:     "3001",
		webPortStr:         "3000",
		sandbox:            false,
		dockerSock:         "",
		logLevel:           "info",
		persistenceBackend: "sqlite",
		memoryBackend:      "mem0",
		busBackend:         "internal",
	}

	state, err := buildState(a)
	if err != nil {
		t.Fatalf("buildState: %v", err)
	}
	if state.PersistenceBackend != "sqlite" {
		t.Errorf("PersistenceBackend = %q, want sqlite", state.PersistenceBackend)
	}
	if state.PostgresPassword != "" {
		t.Errorf("PostgresPassword should be empty for sqlite, got %q", state.PostgresPassword)
	}
}

// TestInitValidatePostgresFlag verifies --persistence-backend validation.
func TestInitValidatePostgresFlag(t *testing.T) {
	tests := []struct {
		name    string
		backend string
		wantErr bool
	}{
		{"sqlite", "sqlite", false},
		{"postgres", "postgres", false},
		{"invalid", "mysql", true},
		{"empty (default)", "", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			old := initPersistenceBackend
			defer func() { initPersistenceBackend = old }()
			initPersistenceBackend = tt.backend
			err := validateInitFlags()
			if (err != nil) != tt.wantErr {
				t.Errorf("validateInitFlags() err=%v, wantErr=%v", err, tt.wantErr)
			}
		})
	}
}

// TestInitValidatePostgresPort verifies --postgres-port range validation.
func TestInitValidatePostgresPort(t *testing.T) {
	tests := []struct {
		name    string
		port    int
		wantErr bool
	}{
		{"default (0)", 0, false},
		{"valid 5432", 5432, false},
		{"too low", 0 - 1, true},
		{"too high", 65536, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			old := initPostgresPort
			defer func() { initPostgresPort = old }()
			initPostgresPort = tt.port
			err := validateInitFlags()
			if (err != nil) != tt.wantErr {
				t.Errorf("validateInitFlags() err=%v, wantErr=%v", err, tt.wantErr)
			}
		})
	}
}

// TestPostgresLifecycle_InitGeneratesWritableState simulates the init flow
// end-to-end: builds state for postgres, writes init files, re-reads config,
// verifies the password + port survive the round-trip (stop/start cycle
// preservation).
func TestPostgresLifecycle_InitGeneratesWritableState(t *testing.T) {
	dir := t.TempDir()
	a := setupAnswers{
		dir:                mustAbs(t, dir),
		backendPortStr:     "3001",
		webPortStr:         "3000",
		sandbox:            false,
		dockerSock:         "",
		logLevel:           "info",
		persistenceBackend: "postgres",
		memoryBackend:      "mem0",
		busBackend:         "internal",
		postgresPort:       3002,
	}

	state, err := buildState(a)
	if err != nil {
		t.Fatalf("buildState: %v", err)
	}

	// Write files as init would.
	safeDir, err := writeInitFiles(state)
	if err != nil {
		t.Fatalf("writeInitFiles: %v", err)
	}

	// Verify compose.yml contains the postgres service.
	composeBytes, err := os.ReadFile(filepath.Join(safeDir, "compose.yml"))
	if err != nil {
		t.Fatalf("reading compose.yml: %v", err)
	}
	composeYAML := string(composeBytes)
	if !strings.Contains(composeYAML, "postgres:") {
		t.Error("compose.yml should contain postgres service")
	}
	if !strings.Contains(composeYAML, "postgres:18-alpine") {
		t.Error("compose.yml should pin postgres:18-alpine")
	}
	if !strings.Contains(composeYAML, "synthorg-pgdata") {
		t.Error("compose.yml should declare synthorg-pgdata volume")
	}
	if !strings.Contains(composeYAML, "pg_isready") {
		t.Error("compose.yml should include pg_isready healthcheck")
	}
	if !strings.Contains(composeYAML, "SYNTHORG_DATABASE_URL") {
		t.Error("compose.yml should set SYNTHORG_DATABASE_URL on backend")
	}
	if strings.Contains(composeYAML, "SYNTHORG_DB_PATH") {
		t.Error("compose.yml should NOT set SYNTHORG_DB_PATH when postgres selected")
	}

	// Verify config.json persists password + port.
	configBytes, err := os.ReadFile(filepath.Join(safeDir, "config.json"))
	if err != nil {
		t.Fatalf("reading config.json: %v", err)
	}
	var persisted config.State
	if err := json.Unmarshal(configBytes, &persisted); err != nil {
		t.Fatalf("parsing config.json: %v", err)
	}
	if persisted.PersistenceBackend != "postgres" {
		t.Errorf("persisted PersistenceBackend = %q, want postgres", persisted.PersistenceBackend)
	}
	if persisted.PostgresPort != 3002 {
		t.Errorf("persisted PostgresPort = %d, want 3002", persisted.PostgresPort)
	}
	if persisted.PostgresPassword != state.PostgresPassword {
		t.Error("persisted PostgresPassword != original (stop/start preservation would fail)")
	}

	// Verify we can regenerate compose.yml from the persisted state
	// (simulates `synthorg start` reading the state and rendering compose).
	params := compose.ParamsFromState(persisted)
	regenerated, err := compose.Generate(params)
	if err != nil {
		t.Fatalf("regenerate compose: %v", err)
	}
	if !strings.Contains(string(regenerated), persisted.PostgresPassword) {
		t.Error("regenerated compose must contain the persisted password")
	}
}

func mustAbs(t *testing.T, p string) string {
	t.Helper()
	abs, err := filepath.Abs(p)
	if err != nil {
		t.Fatalf("filepath.Abs(%q): %v", p, err)
	}
	return abs
}
