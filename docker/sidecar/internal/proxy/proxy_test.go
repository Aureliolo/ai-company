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
	p := proxy.New(0, al, false, dnat, nil)

	// Use port 0 to get a random free port -- but our Start binds to
	// the configured port. Use a free port listener instead.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	ln.Close()

	p2 := proxy.New(uint16(port), al, false, dnat, nil)
	if err := p2.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}

	// Verify we can connect to the proxy port.
	conn, err := net.DialTimeout("tcp", ln.Addr().String(), time.Second)
	if err != nil {
		t.Fatalf("DialTimeout: %v", err)
	}
	conn.Close()

	_ = p
	if err := p2.Shutdown(t.Context()); err != nil {
		t.Errorf("Shutdown: %v", err)
	}
}

func TestProxyCreation(t *testing.T) {
	al := allowlist.New([]config.HostPort{
		{Host: "127.0.0.1", Port: 8080},
	}, true, 0)
	dnat := proxy.NewDNATManager(15001, true)
	p := proxy.New(15001, al, false, dnat, nil)
	if p == nil {
		t.Fatal("expected non-nil proxy")
	}
}

func TestProxySetAllowAll(t *testing.T) {
	al := allowlist.New(nil, false, 0)
	dnat := proxy.NewDNATManager(15001, true)
	p := proxy.New(15001, al, false, dnat, nil)

	p.SetAllowAll(true)
	// No panic, state change accepted.

	p.SetAllowAll(false)
	// Toggle back.
}
