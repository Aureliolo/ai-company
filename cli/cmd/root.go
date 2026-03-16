// Package cmd defines the CLI commands for SynthOrg.
package cmd

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/spf13/cobra"
)

var (
	dataDir    string
	skipVerify bool
)

var rootCmd = &cobra.Command{
	Use:   "synthorg",
	Short: "SynthOrg CLI — manage your synthetic organization",
	Long: `SynthOrg CLI manages the lifecycle of your synthetic organization.

Run 'synthorg init' to set up a new installation, then 'synthorg start'
to launch the backend and web dashboard containers.`,
	SilenceUsage:  true,
	SilenceErrors: true,
}

func init() {
	rootCmd.PersistentFlags().StringVar(&dataDir, "data-dir", "", "data directory (default: platform-appropriate)")
	rootCmd.PersistentFlags().BoolVar(&skipVerify, "skip-verify", false,
		"skip container image signature and provenance verification (NOT RECOMMENDED)")

	// Allow SYNTHORG_SKIP_VERIFY env var as fallback for CI/air-gapped environments.
	if v := os.Getenv("SYNTHORG_SKIP_VERIFY"); v != "" {
		switch strings.ToLower(v) {
		case "1", "true", "yes":
			skipVerify = true
		}
	}
}

// resolveDataDir returns the effective data directory, using the flag value or
// the platform default. Symlinks are resolved to prevent traversal issues.
func resolveDataDir() string {
	dir := dataDir
	if dir == "" {
		dir = config.DataDir()
	}
	// Resolve symlinks to prevent traversal.
	if resolved, err := filepath.EvalSymlinks(dir); err == nil {
		return resolved
	}
	return dir
}

// safeStateDir returns a validated absolute path from the loaded state's DataDir.
// This satisfies CodeQL's go/path-injection by applying SecurePath at the call site.
func safeStateDir(state config.State) (string, error) {
	return config.SecurePath(state.DataDir)
}

// isInteractive returns true if stdin is a terminal (not piped or in CI).
func isInteractive() bool {
	fi, err := os.Stdin.Stat()
	if err != nil {
		return false
	}
	return fi.Mode()&os.ModeCharDevice != 0
}

// isTransportError returns true when err is caused by a network/transport
// problem (DNS failure, connection refused, timeout) rather than a
// cryptographic verification failure. Used to conditionally suggest
// --skip-verify only when the issue is connectivity, not a tampered image.
func isTransportError(err error) bool {
	if errors.Is(err, context.DeadlineExceeded) {
		return true
	}
	var netErr *net.OpError
	if errors.As(err, &netErr) {
		return true
	}
	var dnsErr *net.DNSError
	if errors.As(err, &dnsErr) {
		return true
	}
	// Check for net.Error interface (covers timeout errors from HTTP clients).
	var netIface net.Error
	if errors.As(err, &netIface) && netIface.Timeout() {
		return true
	}
	return false
}

// Execute runs the root command.
func Execute() error {
	if err := rootCmd.Execute(); err != nil {
		_, _ = fmt.Fprintln(rootCmd.ErrOrStderr(), err)
		return err
	}
	return nil
}
