// Package cmd defines the CLI commands for SynthOrg.
package cmd

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/spf13/cobra"
)

// Flag variables for persistent flags.
var (
	flagDataDir    string
	flagSkipVerify bool
	flagQuiet      bool
	flagVerbose    int
	flagNoColor    bool
	flagPlain      bool
	flagJSON       bool
	flagYes        bool
)

var rootCmd = &cobra.Command{
	Use:   "synthorg",
	Short: "SynthOrg CLI -- manage your synthetic organization",
	Long: `SynthOrg CLI manages the lifecycle of your synthetic organization.

Run 'synthorg init' to set up a new installation, then 'synthorg start'
to launch the backend and web dashboard containers.`,
	SilenceUsage:  true,
	SilenceErrors: true,
	PersistentPreRunE: func(cmd *cobra.Command, _ []string) error {
		return setupGlobalOpts(cmd)
	},
}

func init() {
	pf := rootCmd.PersistentFlags()
	pf.StringVar(&flagDataDir, "data-dir", "", "data directory (default: platform-appropriate)")
	pf.BoolVar(&flagSkipVerify, "skip-verify", false,
		"skip container image signature and provenance verification (NOT RECOMMENDED)")
	pf.BoolVarP(&flagQuiet, "quiet", "q", false, "suppress non-essential output (errors only)")
	pf.CountVarP(&flagVerbose, "verbose", "v", "increase verbosity (-v=verbose, -vv=trace)")
	pf.BoolVar(&flagNoColor, "no-color", false, "disable ANSI color output")
	pf.BoolVar(&flagPlain, "plain", false, "ASCII-only output (no Unicode, no spinners, no box drawing)")
	pf.BoolVar(&flagJSON, "json", false, "output machine-readable JSON")
	pf.BoolVarP(&flagYes, "yes", "y", false, "assume yes for all prompts (non-interactive mode)")

	// Allow SYNTHORG_SKIP_VERIFY / SYNTHORG_NO_VERIFY env vars as fallback.
	if envBool(EnvNoVerify) || envBool(EnvSkipVerify) {
		flagSkipVerify = true
	}
}

// setupGlobalOpts resolves the effective configuration from flags, env vars,
// and config file, then stores GlobalOpts in the command context.
func setupGlobalOpts(cmd *cobra.Command) error {
	// Validate mutual exclusivity.
	if flagQuiet && flagVerbose > 0 {
		return fmt.Errorf("--quiet and --verbose are mutually exclusive")
	}
	if flagPlain && flagJSON {
		return fmt.Errorf("--plain and --json are mutually exclusive")
	}

	// Resolve --no-color from env if flag not explicitly set.
	noColor := flagNoColor
	if !cmd.Flags().Changed("no-color") && noColorFromEnv() {
		noColor = true
	}

	// Resolve --quiet from env if flag not explicitly set.
	quiet := flagQuiet
	if !cmd.Flags().Changed("quiet") && envBool("SYNTHORG_QUIET") {
		quiet = true
	}

	// Resolve --yes from env if flag not explicitly set.
	yes := flagYes
	if !cmd.Flags().Changed("yes") && envBool("SYNTHORG_YES") {
		yes = true
	}

	opts := &GlobalOpts{
		DataDir:    resolveDataDir(),
		SkipVerify: flagSkipVerify,
		Quiet:      quiet,
		Verbose:    flagVerbose,
		NoColor:    noColor,
		Plain:      flagPlain,
		JSON:       flagJSON,
		Yes:        yes,
		Hints:      "auto", // default; will be overridden by config in PR 2
	}

	cmd.SetContext(SetGlobalOpts(cmd.Context(), opts))
	return nil
}

// resolveDataDir returns the effective data directory, using the flag value,
// env var, or the platform default. Symlinks are resolved to prevent traversal.
func resolveDataDir() string {
	dir := flagDataDir
	if dir == "" {
		dir = envString(EnvDataDir)
	}
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
