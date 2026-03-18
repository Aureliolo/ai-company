package cmd

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

// --- Cobra commands ---

var backupCmd = &cobra.Command{
	Use:   "backup",
	Short: "Manage backups (default: create a new backup)",
	Long: `Create, list, and restore backups of the SynthOrg stack.

Running 'synthorg backup' without a subcommand triggers a manual backup
(equivalent to 'synthorg backup create').`,
	Args: cobra.NoArgs,
	RunE: runBackupCreate,
}

var backupCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Trigger a manual backup",
	Args:  cobra.NoArgs,
	RunE:  runBackupCreate,
}

var backupListCmd = &cobra.Command{
	Use:   "list",
	Short: "List available backups",
	Args:  cobra.NoArgs,
	RunE:  runBackupList,
}

var backupRestoreCmd = &cobra.Command{
	Use:   "restore <backup-id>",
	Short: "Restore from a backup",
	Long: `Restore the SynthOrg stack from a previously created backup.

The --confirm flag is required as a safety gate. A safety backup is
created automatically before the restore begins.

If the restore requires a restart, containers are stopped automatically.
Run 'synthorg start' afterwards to bring the stack back up.`,
	Args: cobra.ExactArgs(1),
	RunE: runBackupRestore,
}

func init() {
	backupRestoreCmd.Flags().Bool("confirm", false, "Confirm the restore operation (required)")
	backupCmd.AddCommand(backupCreateCmd)
	backupCmd.AddCommand(backupListCmd)
	backupCmd.AddCommand(backupRestoreCmd)
	rootCmd.AddCommand(backupCmd)
}

// --- API response types ---

// apiEnvelope is the standard API response wrapper.
type apiEnvelope struct {
	Data    json.RawMessage `json:"data"`
	Error   *string         `json:"error"`
	Success bool            `json:"success"`
}

// backupManifest mirrors the Python BackupManifest model.
type backupManifest struct {
	BackupID        string   `json:"backup_id"`
	Version         string   `json:"version"`
	SynthorgVersion string   `json:"synthorg_version"`
	Timestamp       string   `json:"timestamp"`
	Trigger         string   `json:"trigger"`
	Components      []string `json:"components"`
	DBSchemaVersion int      `json:"db_schema_version"`
	SizeBytes       int64    `json:"size_bytes"`
	Checksum        string   `json:"checksum"`
}

// backupInfo mirrors the Python BackupInfo model.
type backupInfo struct {
	BackupID   string   `json:"backup_id"`
	Timestamp  string   `json:"timestamp"`
	Trigger    string   `json:"trigger"`
	Components []string `json:"components"`
	SizeBytes  int64    `json:"size_bytes"`
	Compressed bool     `json:"compressed"`
}

// restoreResponse mirrors the Python RestoreResponse model.
type restoreResponse struct {
	Manifest           backupManifest `json:"manifest"`
	RestoredComponents []string       `json:"restored_components"`
	SafetyBackupID     string         `json:"safety_backup_id"`
	RestartRequired    bool           `json:"restart_required"`
}

// restoreRequest is the JSON body sent to POST /admin/backups/restore.
type restoreRequest struct {
	BackupID string `json:"backup_id"`
	Confirm  bool   `json:"confirm"`
}

// --- Helper functions ---

var backupIDRe = regexp.MustCompile(`^[0-9a-f]{12}$`)

// isValidBackupID checks whether id matches the 12-char hex pattern.
func isValidBackupID(id string) bool {
	return backupIDRe.MatchString(id)
}

// componentsString joins component names with ", ".
func componentsString(components []string) string {
	return strings.Join(components, ", ")
}

// formatSize converts bytes to a human-readable string.
func formatSize(b int64) string {
	const (
		kb = 1024
		mb = kb * 1024
		gb = mb * 1024
	)
	switch {
	case b >= gb:
		return fmt.Sprintf("%.1f GB", float64(b)/float64(gb))
	case b >= mb:
		return fmt.Sprintf("%.1f MB", float64(b)/float64(mb))
	case b >= kb:
		return fmt.Sprintf("%.1f KB", float64(b)/float64(kb))
	default:
		return fmt.Sprintf("%d B", b)
	}
}

// backupAPIRequest performs an HTTP request to the backup API and returns
// the response body, HTTP status code, and any transport-level error.
func backupAPIRequest(ctx context.Context, port int, method, path string, body []byte, timeout time.Duration) ([]byte, int, error) {
	apiURL := fmt.Sprintf("http://localhost:%d/api/v1/admin/backups%s", port, path)
	client := &http.Client{Timeout: timeout}

	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, apiURL, bodyReader)
	if err != nil {
		return nil, 0, fmt.Errorf("building request: %w", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("backend unreachable: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20)) // 1 MB limit
	if err != nil {
		return nil, 0, fmt.Errorf("reading response: %w", err)
	}
	return respBody, resp.StatusCode, nil
}

// parseAPIResponse decodes the ApiResponse envelope and returns the raw data
// payload on success, or an error containing the envelope's error message.
func parseAPIResponse(raw []byte) (json.RawMessage, error) {
	var env apiEnvelope
	if err := json.Unmarshal(raw, &env); err != nil {
		return nil, fmt.Errorf("parsing response: %w", err)
	}
	if !env.Success {
		msg := "unknown error"
		if env.Error != nil {
			msg = *env.Error
		}
		return nil, errors.New(msg)
	}
	return env.Data, nil
}

// --- Command implementations ---

func runBackupCreate(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	out := ui.NewUI(cmd.OutOrStdout())
	out.Step("Creating backup...")

	body, statusCode, err := backupAPIRequest(ctx, state.BackendPort, http.MethodPost, "", nil, 30*time.Second)
	if err != nil {
		return fmt.Errorf("creating backup: %w", err)
	}

	if statusCode < 200 || statusCode >= 300 {
		data, parseErr := parseAPIResponse(body)
		_ = data
		msg := "backup failed"
		if parseErr != nil {
			msg = parseErr.Error()
		}
		out.Error(msg)
		return nil
	}

	data, err := parseAPIResponse(body)
	if err != nil {
		out.Error(err.Error())
		return nil
	}

	var manifest backupManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return fmt.Errorf("parsing backup manifest: %w", err)
	}

	out.Success("Backup created successfully")
	out.KeyValue("Backup ID", manifest.BackupID)
	out.KeyValue("Timestamp", manifest.Timestamp)
	out.KeyValue("Trigger", manifest.Trigger)
	out.KeyValue("Components", componentsString(manifest.Components))
	out.KeyValue("Size", formatSize(manifest.SizeBytes))
	out.KeyValue("Checksum", manifest.Checksum)
	out.KeyValue("SynthOrg version", manifest.SynthorgVersion)
	out.KeyValue("DB schema version", fmt.Sprintf("%d", manifest.DBSchemaVersion))

	return nil
}

func runBackupList(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	out := ui.NewUI(cmd.OutOrStdout())

	body, statusCode, err := backupAPIRequest(ctx, state.BackendPort, http.MethodGet, "", nil, 10*time.Second)
	if err != nil {
		return fmt.Errorf("listing backups: %w", err)
	}

	if statusCode < 200 || statusCode >= 300 {
		data, parseErr := parseAPIResponse(body)
		_ = data
		msg := "failed to list backups"
		if parseErr != nil {
			msg = parseErr.Error()
		}
		out.Error(msg)
		return nil
	}

	data, err := parseAPIResponse(body)
	if err != nil {
		out.Error(err.Error())
		return nil
	}

	var backups []backupInfo
	if err := json.Unmarshal(data, &backups); err != nil {
		return fmt.Errorf("parsing backup list: %w", err)
	}

	if len(backups) == 0 {
		out.Warn("No backups found")
		out.Hint("Run 'synthorg backup' to create one")
		return nil
	}

	headers := []string{"ID", "TIMESTAMP", "TRIGGER", "COMPONENTS", "SIZE", "COMPRESSED"}
	rows := make([][]string, 0, len(backups))
	for _, b := range backups {
		compressed := "no"
		if b.Compressed {
			compressed = "yes"
		}
		rows = append(rows, []string{
			b.BackupID,
			b.Timestamp,
			b.Trigger,
			componentsString(b.Components),
			formatSize(b.SizeBytes),
			compressed,
		})
	}
	out.Table(headers, rows)

	return nil
}

func runBackupRestore(cmd *cobra.Command, args []string) error {
	ctx := cmd.Context()
	backupID := args[0]

	// Validate backup ID format before anything else.
	if !isValidBackupID(backupID) {
		return fmt.Errorf("invalid backup ID %q: must be a 12-character hex string", backupID)
	}

	out := ui.NewUI(cmd.OutOrStdout())

	// Check --confirm flag.
	confirm, _ := cmd.Flags().GetBool("confirm")
	if !confirm {
		out.Error("Restore requires the --confirm flag as a safety gate")
		out.Hint(fmt.Sprintf("Run 'synthorg backup restore %s --confirm' to proceed", backupID))
		return nil
	}

	dir := resolveDataDir()
	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	out.Step("Restoring from backup " + backupID + "...")

	reqBody, err := json.Marshal(restoreRequest{
		BackupID: backupID,
		Confirm:  true,
	})
	if err != nil {
		return fmt.Errorf("building restore request: %w", err)
	}

	body, statusCode, err := backupAPIRequest(ctx, state.BackendPort, http.MethodPost, "/restore", reqBody, 30*time.Second)
	if err != nil {
		return fmt.Errorf("restoring backup: %w", err)
	}

	if statusCode < 200 || statusCode >= 300 {
		return handleRestoreError(out, body, statusCode, backupID)
	}

	data, err := parseAPIResponse(body)
	if err != nil {
		out.Error(err.Error())
		return nil
	}

	var resp restoreResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return fmt.Errorf("parsing restore response: %w", err)
	}

	out.Success("Restore completed successfully")
	out.KeyValue("Safety backup ID", resp.SafetyBackupID)
	out.KeyValue("Restored components", componentsString(resp.RestoredComponents))

	if resp.RestartRequired {
		return handleRestartAfterRestore(ctx, cmd, out, state)
	}

	return nil
}

// handleRestoreError displays a user-friendly error for restore API failures.
func handleRestoreError(out *ui.UI, body []byte, statusCode int, backupID string) error {
	_, parseErr := parseAPIResponse(body)
	msg := "restore failed"
	if parseErr != nil {
		msg = parseErr.Error()
	}

	switch statusCode {
	case http.StatusNotFound:
		out.Error(fmt.Sprintf("Backup not found: %s", backupID))
		out.Hint("Run 'synthorg backup list' to see available backups")
	case http.StatusConflict:
		out.Error(msg)
	case http.StatusUnprocessableEntity:
		out.Error(msg)
	default:
		out.Error(msg)
	}
	return nil
}

// handleRestartAfterRestore stops containers when a restore requires restart.
func handleRestartAfterRestore(ctx context.Context, cmd *cobra.Command, out *ui.UI, state config.State) error {
	out.KeyValue("Restart required", "yes")

	safeDir, err := safeStateDir(state)
	if err != nil {
		out.Warn("Could not determine data directory for container stop")
		out.Hint("Run 'synthorg stop' then 'synthorg start' manually")
		return nil
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		out.Hint("Run 'synthorg start' to bring the stack back up")
		return nil
	}

	info, err := docker.Detect(ctx)
	if err != nil {
		out.Warn(fmt.Sprintf("Could not detect Docker: %v", err))
		out.Hint("Run 'synthorg stop' then 'synthorg start' manually")
		return nil
	}

	out.Step("Stopping containers for restart...")
	if err := composeRun(ctx, cmd, info, safeDir, "down"); err != nil {
		out.Warn(fmt.Sprintf("Could not stop containers: %v", err))
		out.Hint("Run 'synthorg stop' then 'synthorg start' manually")
		return nil
	}

	out.Hint("Run 'synthorg start' to bring the stack back up")
	return nil
}
