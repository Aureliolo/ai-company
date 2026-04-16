package cmd

import (
	"bytes"
	"strings"
	"testing"

	"github.com/spf13/cobra"
)

// newTestCmd returns a minimal *cobra.Command with OutOrStdout/ErrOrStderr
// redirected to buffers so applyTunables's trust-transfer warning can be
// captured and asserted against.
func newTestCmd() (*cobra.Command, *bytes.Buffer) {
	c := &cobra.Command{Use: "test"}
	errBuf := &bytes.Buffer{}
	c.SetOut(&bytes.Buffer{})
	c.SetErr(errBuf)
	return c, errBuf
}

func TestApplyTunables_DefaultRegistryKeepsVerification(t *testing.T) {
	c, errBuf := newTestCmd()
	opts := &GlobalOpts{Hints: "auto"}

	if err := applyTunables(c, opts); err != nil {
		t.Fatalf("applyTunables: %v", err)
	}
	if opts.SkipVerify {
		t.Error("SkipVerify = true on default registry; want false")
	}
	if opts.Tunables.CustomRegistry {
		t.Error("Tunables.CustomRegistry = true on default registry; want false")
	}
	if strings.Contains(errBuf.String(), "DISABLED") {
		t.Errorf("trust-transfer warning fired on default registry: %q", errBuf.String())
	}
}

func TestApplyTunables_CustomRegistryDisablesVerification(t *testing.T) {
	t.Setenv("SYNTHORG_REGISTRY_HOST", "my.registry.example")

	c, errBuf := newTestCmd()
	opts := &GlobalOpts{Hints: "auto"}

	if err := applyTunables(c, opts); err != nil {
		t.Fatalf("applyTunables: %v", err)
	}
	if !opts.SkipVerify {
		t.Error("SkipVerify = false on custom registry; want true")
	}
	if !opts.Tunables.CustomRegistry {
		t.Error("Tunables.CustomRegistry = false on custom registry; want true")
	}
	if !strings.Contains(errBuf.String(), "DISABLED") {
		t.Errorf("trust-transfer warning missing; stderr = %q", errBuf.String())
	}
}

func TestApplyTunables_CustomRegistryQuietSuppressesWarning(t *testing.T) {
	t.Setenv("SYNTHORG_DHI_REGISTRY", "private.docker.example")

	c, errBuf := newTestCmd()
	opts := &GlobalOpts{Hints: "auto", Quiet: true}

	if err := applyTunables(c, opts); err != nil {
		t.Fatalf("applyTunables: %v", err)
	}
	if !opts.SkipVerify {
		t.Error("SkipVerify = false on custom registry; want true even when --quiet")
	}
	if strings.Contains(errBuf.String(), "DISABLED") {
		t.Errorf("--quiet should suppress trust-transfer warning; stderr = %q", errBuf.String())
	}
}
