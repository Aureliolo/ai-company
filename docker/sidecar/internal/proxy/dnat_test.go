package proxy_test

import (
	"testing"

	"github.com/Aureliolo/synthorg/sidecar/internal/proxy"
)

func TestDNATManagerRulesEmpty(t *testing.T) {
	mgr := proxy.NewDNATManager(15001, true)
	if len(mgr.Rules()) != 0 {
		t.Error("expected no rules before Setup")
	}
}

func TestDNATManagerCreation(t *testing.T) {
	// Verify manager can be created without panic.
	mgr := proxy.NewDNATManager(15001, true)
	if mgr == nil {
		t.Fatal("expected non-nil manager")
	}
}

func TestDNATManagerDNSBlocked(t *testing.T) {
	mgr := proxy.NewDNATManager(15001, false)
	if mgr == nil {
		t.Fatal("expected non-nil manager")
	}
	// Cannot test Setup without iptables, but verify creation is fine.
}
