package cmd

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/spf13/cobra"
)

var (
	logFollow     bool
	logTail       string
	logSince      string
	logUntil      string
	logTimestamps bool
	logNoPrefix   bool
)

// serviceNamePattern validates service names to prevent command injection via
// compose arguments (only alphanumeric, hyphens, and underscores).
var serviceNamePattern = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

// timeFilterPattern validates --since/--until values (timestamps, durations).
var timeFilterPattern = regexp.MustCompile(`^[0-9a-zA-Z:.+\-TZ]+$`)

var logsCmd = &cobra.Command{
	Use:   "logs [service]",
	Short: "Show container logs",
	Long:  "Passes through to 'docker compose logs'. Optionally specify a service (backend, web).",
	RunE:  runLogs,
}

func init() {
	logsCmd.Flags().BoolVarP(&logFollow, "follow", "f", false, "follow log output")
	logsCmd.Flags().StringVar(&logTail, "tail", "100", "number of lines to show from end")
	logsCmd.Flags().StringVar(&logSince, "since", "", "show logs since timestamp or relative (e.g. 2024-01-01, 1h)")
	logsCmd.Flags().StringVar(&logUntil, "until", "", "show logs until timestamp or relative")
	logsCmd.Flags().BoolVarP(&logTimestamps, "timestamps", "t", false, "show timestamps")
	logsCmd.Flags().BoolVar(&logNoPrefix, "no-log-prefix", false, "don't print service prefix in logs")
	rootCmd.AddCommand(logsCmd)
}

func runLogs(cmd *cobra.Command, args []string) error {
	ctx := cmd.Context()

	state, err := config.Load(GetGlobalOpts(ctx).DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("compose.yml not found in %s -- run 'synthorg init' first", safeDir)
	}

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}

	// Validate --tail value.
	tail := strings.TrimSpace(logTail)
	if tail != "all" {
		if n, err := strconv.Atoi(tail); err != nil || n <= 0 {
			return fmt.Errorf("--tail must be a positive integer or 'all', got %q", logTail)
		}
	}

	// Validate --since/--until format (allow timestamps, durations, Docker-accepted values).
	for _, tv := range []struct{ flag, val string }{{"--since", logSince}, {"--until", logUntil}} {
		if tv.val != "" && !timeFilterPattern.MatchString(tv.val) {
			return fmt.Errorf("%s value %q contains unexpected characters", tv.flag, tv.val)
		}
	}

	// Validate service name arguments.
	for _, svc := range args {
		if !serviceNamePattern.MatchString(svc) {
			return fmt.Errorf("invalid service name %q: must be alphanumeric, hyphens, or underscores", svc)
		}
	}

	composeArgs := []string{"logs", "--tail", tail}
	if logFollow {
		composeArgs = append(composeArgs, "-f")
	}
	if logSince != "" {
		composeArgs = append(composeArgs, "--since", logSince)
	}
	if logUntil != "" {
		composeArgs = append(composeArgs, "--until", logUntil)
	}
	if logTimestamps {
		composeArgs = append(composeArgs, "--timestamps")
	}
	if logNoPrefix {
		composeArgs = append(composeArgs, "--no-log-prefix")
	}
	// Use -- separator to prevent service names from being parsed as flags.
	composeArgs = append(composeArgs, "--")
	composeArgs = append(composeArgs, args...)

	return composeRun(ctx, cmd, info, safeDir, composeArgs...)
}
