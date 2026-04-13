package proxy_test

import (
	"net"
	"testing"
	"time"

	"github.com/Aureliolo/synthorg/sidecar/internal/allowlist"
	"github.com/Aureliolo/synthorg/sidecar/internal/config"
	"github.com/Aureliolo/synthorg/sidecar/internal/proxy"
)

func TestProxyStartStop(t *testing.T) {
	al := allowlist.New(nil, true, 0)
	dnat := proxy.NewDNATManager(0, true)

	// Use port 0 to get a random free port -- but our Start binds to
	// the configured port. Use a free port listener instead.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	ln.Close()

	p := proxy.New(uint16(port), al, dnat, nil)
	if err := p.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}

	// Verify we can connect to the proxy port.
	conn, err := net.DialTimeout("tcp", ln.Addr().String(), time.Second)
	if err != nil {
		t.Fatalf("DialTimeout: %v", err)
	}
	conn.Close()

	if err := p.Shutdown(t.Context()); err != nil {
		t.Errorf("Shutdown: %v", err)
	}
}

func TestProxyCreation(t *testing.T) {
	al := allowlist.New([]config.HostPort{
		{Host: "127.0.0.1", Port: 8080},
	}, true, 0)
	dnat := proxy.NewDNATManager(15001, true)
	p := proxy.New(15001, al, dnat, nil)
	if p == nil {
		t.Fatal("expected non-nil proxy")
	}
}

func TestProxyAllowAllDelegatedToAllowlist(t *testing.T) {
	// allow-all state is owned by the Allowlist, not the Proxy.
	// Toggling via Allowlist.UpdateRules should be reflected in the
	// proxy's enforcement without any direct Proxy API call.
	al := allowlist.New(nil, false, 0)
	dnat := proxy.NewDNATManager(15001, true)
	p := proxy.New(15001, al, dnat, nil)
	if p == nil {
		t.Fatal("expected non-nil proxy")
	}

	// Toggle allowAll via the allowlist (simulates admin API path).
	al.UpdateRules(nil, true)
	if !al.IsAllowAll() {
		t.Error("expected allow-all to be true after UpdateRules")
	}

	al.UpdateRules(nil, false)
	if al.IsAllowAll() {
		t.Error("expected allow-all to be false after UpdateRules")
	}
}
