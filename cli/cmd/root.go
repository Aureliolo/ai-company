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
	// IMPORTANT: Cobra does NOT chain PersistentPreRunE. If any subcommand
	// defines its own PersistentPreRunE or PreRunE, this hook is silently
	// skipped and GlobalOpts will fall back to zero-value defaults. Always
	// call setupGlobalOpts explicitly in any subcommand pre-run hook.
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

	// Note: SYNTHORG_SKIP_VERIFY / SYNTHORG_NO_VERIFY env vars are resolved
	// inside setupGlobalOpts alongside all other env var overrides.
}

// setupGlobalOpts resolves the effective configuration from flags, env vars,
// and config file, then stores GlobalOpts in the command context.
func setupGlobalOpts(cmd *cobra.Command) error {
	noColor, quiet, yes, skipVerify := resolveEnvOverrides()

	if quiet && flagVerbose > 0 {
		return fmt.Errorf("--quiet and --verbose are mutually exclusive")
	}
	if flagPlain && flagJSON {
		return fmt.Errorf("--plain and --json are mutually exclusive")
	}

	opts := &GlobalOpts{
		DataDir:    resolveDataDir(),
		SkipVerify: skipVerify,
		Quiet:      quiet,
		Verbose:    flagVerbose,
		NoColor:    noColor,
		Plain:      flagPlain,
		JSON:       flagJSON,
		Yes:        yes,
		Hints:      "auto",
	}

	applyConfigOverrides(opts)

	if !validHintsMode(opts.Hints) {
		return fmt.Errorf("invalid hints mode %q: must be always, auto, or never", opts.Hints)
	}

	cmd.SetContext(SetGlobalOpts(cmd.Context(), opts))
	return nil
}

// resolveEnvOverrides merges environment variable overrides with flag values.
// Use flag variables directly (already populated by Cobra) rather than
// cmd.Flags().Changed() which only sees local flags on subcommands.
func resolveEnvOverrides() (noColor, quiet, yes, skipVerify bool) {
	noColor = flagNoColor
	if !flagNoColor && noColorFromEnv() {
		noColor = true
	}
	quiet = flagQuiet
	if !flagQuiet && envBool(EnvQuiet) {
		quiet = true
	}
	yes = flagYes
	if !flagYes && envBool(EnvYes) {
		yes = true
	}
	skipVerify = flagSkipVerify
	if !flagSkipVerify && (envBool(EnvNoVerify) || envBool(EnvSkipVerify)) {
		skipVerify = true
	}
	return
}

// applyConfigOverrides loads persisted config and applies display preferences.
// Only applies when neither a flag nor an env var already set the value,
// preserving flag > env > config > default precedence.
func applyConfigOverrides(opts *GlobalOpts) {
	state, loadErr := config.Load(opts.DataDir)
	if loadErr != nil {
		return
	}
	if state.Hints != "" {
		opts.Hints = state.Hints
	}
	// Only apply color config when no flag AND no env var overrode it.
	// Check opts.NoColor (which reflects env) rather than flagNoColor alone.
	if !flagNoColor && !opts.NoColor {
		if state.Color == "never" {
			opts.NoColor = true
		}
	}
	if flagNoColor || opts.NoColor {
		// Flag or env already forced no-color; config "always" must not override.
	} else if state.Color == "always" {
		opts.NoColor = false
	}
	if !flagJSON && !opts.JSON {
		if state.Output == "json" {
			opts.JSON = true
		}
	}
}

// resolveDataDir returns the effective data directory, using the flag value,
// env var, or the platform default. The result is normalized to an absolute
// path and symlinks are resolved to prevent traversal.
func resolveDataDir() string {
	dir := flagDataDir
	if dir == "" {
		dir = os.Getenv(EnvDataDir)
	}
	if dir == "" {
		dir = config.DataDir()
	}
	// Normalize to absolute path before any filesystem use.
	if abs, err := filepath.Abs(dir); err == nil {
		dir = abs
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
// Prefer GlobalOpts.ShouldPrompt() which additionally respects --yes.
// This function is retained for destructive commands (wipe, uninstall) where
// the --yes flag and TTY check must be evaluated separately.
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
		// Don't print ChildExitError to stderr -- its internal message
		// ("re-launched CLI exited with code N") is not user-facing.
		// main.go handles the exit code propagation.
		var ce *ChildExitError
		if !errors.As(err, &ce) {
			_, _ = fmt.Fprintln(rootCmd.ErrOrStderr(), err)
		}
		return err
	}
	return nil
}
