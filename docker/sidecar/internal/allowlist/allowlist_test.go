package allowlist_test

import (
	"testing"

	"github.com/Aureliolo/synthorg/sidecar/internal/allowlist"
	"github.com/Aureliolo/synthorg/sidecar/internal/config"
)

func newTestAllowlist(hosts []config.HostPort, loopback bool) *allowlist.Allowlist {
	// resolveInterval=0 disables background resolution.
	return allowlist.New(hosts, loopback, 0)
}

func TestIsAllowedIPMatch(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "1.2.3.4", Port: 443},
	}, false)
	if !al.IsAllowedIP("1.2.3.4", 443) {
		t.Error("expected 1.2.3.4:443 to be allowed")
	}
}

func TestIsAllowedIPNoMatch(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "1.2.3.4", Port: 443},
	}, false)
	if al.IsAllowedIP("5.6.7.8", 443) {
		t.Error("expected 5.6.7.8:443 to be denied")
	}
}

func TestIsAllowedIPWrongPort(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "1.2.3.4", Port: 443},
	}, false)
	if al.IsAllowedIP("1.2.3.4", 80) {
		t.Error("expected 1.2.3.4:80 to be denied (wrong port)")
	}
}

func TestIsAllowedIPEmpty(t *testing.T) {
	al := newTestAllowlist(nil, false)
	if al.IsAllowedIP("1.2.3.4", 443) {
		t.Error("expected empty allowlist to deny all")
	}
}

func TestLoopbackAllowed(t *testing.T) {
	al := newTestAllowlist(nil, true)
	if !al.IsAllowedIP("127.0.0.1", 8080) {
		t.Error("expected loopback to be allowed when enabled")
	}
	if !al.IsAllowedIP("127.0.0.2", 3000) {
		t.Error("expected 127.0.0.2 to be allowed as loopback")
	}
}

func TestLoopbackDenied(t *testing.T) {
	al := newTestAllowlist(nil, false)
	if al.IsAllowedIP("127.0.0.1", 8080) {
		t.Error("expected loopback to be denied when disabled")
	}
}

func TestIsAllowedHostnameMatch(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "api.example.com", Port: 443},
	}, false)
	if !al.IsAllowedHostname("api.example.com") {
		t.Error("expected api.example.com to be allowed")
	}
}

func TestIsAllowedHostnameCaseInsensitive(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "api.example.com", Port: 443},
	}, false)
	if !al.IsAllowedHostname("API.Example.COM") {
		t.Error("expected case-insensitive hostname match")
	}
}

func TestIsAllowedHostnameNoMatch(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "api.example.com", Port: 443},
	}, false)
	if al.IsAllowedHostname("evil.com") {
		t.Error("expected evil.com to be denied")
	}
}

func TestMultipleHostsSameName(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "api.example.com", Port: 443},
		{Host: "api.example.com", Port: 8443},
	}, false)
	if !al.IsAllowedHostname("api.example.com") {
		t.Error("expected api.example.com to be allowed")
	}
}

func TestUpdateRules(t *testing.T) {
	al := newTestAllowlist([]config.HostPort{
		{Host: "1.2.3.4", Port: 443},
	}, false)

	if !al.IsAllowedIP("1.2.3.4", 443) {
		t.Fatal("precondition: 1.2.3.4:443 should be allowed")
	}

	al.UpdateRules([]config.HostPort{
		{Host: "5.6.7.8", Port: 80},
	}, false)

	if al.IsAllowedIP("1.2.3.4", 443) {
		t.Error("expected old rule to be removed after update")
	}
	if !al.IsAllowedIP("5.6.7.8", 80) {
		t.Error("expected new rule to be active after update")
	}
}

func TestUpdateRulesAllowAll(t *testing.T) {
	al := newTestAllowlist(nil, false)

	if al.IsAllowedIP("1.2.3.4", 443) {
		t.Fatal("precondition: should be denied")
	}

	al.UpdateRules(nil, true)

	if !al.IsAllowedIP("1.2.3.4", 443) {
		t.Error("expected allow_all to permit any connection")
	}
}
