package cmd

import (
	"bytes"
	"strings"
	"testing"
)

// These tests sandbox the package-level rootCmd: each one rewires
// stdout/err to fresh buffers, points --data-dir at a throwaway temp
// directory (so a developer's real or malformed config.json cannot
// poison the test), and registers a t.Cleanup that restores the prior
// writers and clears the args. Do NOT call t.Parallel() -- rootCmd is a
// package-level singleton and parallel mutation of its writers would
// race with any other test that touches rootCmd.

// TestWorkerCmd_BareInvocationPrintsHelp verifies that `synthorg worker`
// with no subcommand renders the help text (exit 0) instead of silently
// succeeding without doing anything -- the behaviour the audit flagged.
func TestWorkerCmd_BareInvocationPrintsHelp(t *testing.T) {
	root := rootCmd
	prevOut, prevErr := root.OutOrStdout(), root.ErrOrStderr()
	t.Cleanup(func() {
		root.SetOut(prevOut)
		root.SetErr(prevErr)
		root.SetArgs(nil)
	})

	dataDir := t.TempDir()
	out, errOut := &bytes.Buffer{}, &bytes.Buffer{}
	root.SetOut(out)
	root.SetErr(errOut)
	root.SetArgs([]string{"--data-dir", dataDir, "worker"})

	if err := root.Execute(); err != nil {
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
	root := rootCmd
	prevOut, prevErr := root.OutOrStdout(), root.ErrOrStderr()
	t.Cleanup(func() {
		root.SetOut(prevOut)
		root.SetErr(prevErr)
		root.SetArgs(nil)
	})

	dataDir := t.TempDir()
	out, errOut := &bytes.Buffer{}, &bytes.Buffer{}
	root.SetOut(out)
	root.SetErr(errOut)
	root.SetArgs([]string{"--data-dir", dataDir, "worker", "bogus-subcommand"})

	err := root.Execute()
	if err == nil {
		t.Fatalf("Execute with unknown subcommand: want error, got nil; stdout=%q stderr=%q", out.String(), errOut.String())
	}
	if !strings.Contains(err.Error(), "unknown command") {
		t.Errorf("error %q does not mention 'unknown command'", err.Error())
	}
}
