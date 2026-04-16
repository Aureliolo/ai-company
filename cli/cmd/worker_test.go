package cmd

import (
	"bytes"
	"strings"
	"testing"
)

// These tests sandbox the package-level rootCmd: each one rewires
// stdout/err to fresh buffers, points --data-dir at a throwaway temp
// directory (so a developer's real or malformed config.json cannot
// poison the test), and registers a t.Cleanup that restores prior
// writers, clears SetArgs, and ALSO resets the Cobra-bound global flag
// values. Clearing only SetArgs is not enough: Cobra's flag parser
// writes the parsed "--data-dir" straight into the package-level
// flagDataDir variable, so the next test (or any test that uses rootCmd)
// would otherwise inherit a now-deleted t.TempDir() path. Do NOT call
// t.Parallel() -- rootCmd is a package-level singleton and parallel
// mutation of its writers and flag bindings would race.

// sandboxRootCmd snapshots rootCmd's writers and bound flag values,
// registers a t.Cleanup that restores them, and returns fresh
// stdout/stderr buffers plus a temp data dir the caller should point
// --data-dir at. Every direct user of rootCmd in tests must go through
// this helper so flag bleed-through between tests stays impossible.
func sandboxRootCmd(t *testing.T) (stdout, stderr *bytes.Buffer, dataDir string) {
	t.Helper()
	root := rootCmd
	prevOut, prevErr := root.OutOrStdout(), root.ErrOrStderr()
	// Snapshot every persistent flag variable bound in init(). The
	// parser writes into these globals during Execute(), so a reset
	// after each test is the only way to guarantee hermetic state.
	prevDataDir := flagDataDir
	prevSkipVerify := flagSkipVerify
	prevQuiet := flagQuiet
	prevVerbose := flagVerbose
	prevNoColor := flagNoColor
	prevPlain := flagPlain
	prevJSON := flagJSON
	prevYes := flagYes
	prevHelpAll := flagHelpAll

	t.Cleanup(func() {
		root.SetOut(prevOut)
		root.SetErr(prevErr)
		root.SetArgs(nil)
		flagDataDir = prevDataDir
		flagSkipVerify = prevSkipVerify
		flagQuiet = prevQuiet
		flagVerbose = prevVerbose
		flagNoColor = prevNoColor
		flagPlain = prevPlain
		flagJSON = prevJSON
		flagYes = prevYes
		flagHelpAll = prevHelpAll
	})

	stdout, stderr = &bytes.Buffer{}, &bytes.Buffer{}
	root.SetOut(stdout)
	root.SetErr(stderr)
	dataDir = t.TempDir()
	return stdout, stderr, dataDir
}

// TestWorkerCmd_BareInvocationPrintsHelp verifies that `synthorg worker`
// with no subcommand renders the help text (exit 0) instead of silently
// succeeding without doing anything -- the behaviour the audit flagged.
func TestWorkerCmd_BareInvocationPrintsHelp(t *testing.T) {
	out, errOut, dataDir := sandboxRootCmd(t)
	rootCmd.SetArgs([]string{"--data-dir", dataDir, "worker"})

	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("Execute: %v; stderr=%q", err, errOut.String())
	}
	combined := out.String() + errOut.String()
	if !strings.Contains(combined, "Available Commands:") {
		t.Errorf("help output missing 'Available Commands:'; got:\n%s", combined)
	}
	if !strings.Contains(combined, "start") {
		t.Errorf("help output missing 'start' subcommand; got:\n%s", combined)
	}
}

// TestWorkerCmd_UnknownSubcommandRejected verifies that `synthorg worker foo`
// returns a usage error rather than silently succeeding.
func TestWorkerCmd_UnknownSubcommandRejected(t *testing.T) {
	out, errOut, dataDir := sandboxRootCmd(t)
	rootCmd.SetArgs([]string{"--data-dir", dataDir, "worker", "bogus-subcommand"})

	err := rootCmd.Execute()
	if err == nil {
		t.Fatalf("Execute with unknown subcommand: want error, got nil; stdout=%q stderr=%q", out.String(), errOut.String())
	}
	if !strings.Contains(err.Error(), "unknown command") {
		t.Errorf("error %q does not mention 'unknown command'", err.Error())
	}
}
