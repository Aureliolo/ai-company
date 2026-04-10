package cmd

import (
	"strings"
	"testing"
)

func TestValidateNatsURL(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name    string
		url     string
		wantErr bool
	}{
		{name: "plain nats scheme", url: "nats://localhost:4222", wantErr: false},
		{name: "tls scheme", url: "tls://nats-prod:4222", wantErr: false},
		{name: "nats+tls scheme", url: "nats+tls://nats-prod:4222", wantErr: false},
		{name: "with credentials", url: "nats://user:pass@host:4222", wantErr: false},
		{name: "no port is fine", url: "nats://localhost", wantErr: false},
		{name: "empty", url: "", wantErr: true},
		{name: "no scheme", url: "localhost:4222", wantErr: true},
		{name: "wrong scheme", url: "http://host:4222", wantErr: true},
		{name: "no host", url: "nats://", wantErr: true},
		// Regression: url.Parse accepts "nats://:4222" with Host = ":4222"
		// so the old `parsed.Host == ""` check missed it.
		{name: "port without host rejected", url: "nats://:4222", wantErr: true},
		{name: "port zero rejected", url: "nats://localhost:0", wantErr: true},
		{name: "port over 65535 rejected", url: "nats://localhost:70000", wantErr: true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			err := validateNatsURL(tc.url)
			if (err != nil) != tc.wantErr {
				t.Errorf("validateNatsURL(%q) error=%v, wantErr=%v", tc.url, err, tc.wantErr)
			}
		})
	}
}

func TestValidateContainerName(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{name: "empty allowed (default)", input: "", wantErr: false},
		{name: "alphanumeric", input: "synthorg-backend", wantErr: false},
		{name: "with underscore", input: "synthorg_backend", wantErr: false},
		{name: "with dot", input: "synthorg.backend", wantErr: false},
		{name: "semicolon rejected", input: "backend;rm", wantErr: true},
		{name: "space rejected", input: "back end", wantErr: true},
		{name: "backtick rejected", input: "back`end", wantErr: true},
		{name: "dollar rejected", input: "back$end", wantErr: true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			err := validateContainerName(tc.input)
			if (err != nil) != tc.wantErr {
				t.Errorf("validateContainerName(%q) error=%v, wantErr=%v", tc.input, err, tc.wantErr)
			}
		})
	}
}

func TestRedactNatsURL(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name         string
		input        string
		mustNotHave  []string
		mustContain  []string
		exactMatch   string
		useExactOnly bool
	}{
		{
			name:         "plain url passes through",
			input:        "nats://localhost:4222",
			exactMatch:   "nats://localhost:4222",
			useExactOnly: true,
		},
		{
			name:        "username and password stripped",
			input:       "nats://admin:secretpassword@nats-prod:4222",
			mustNotHave: []string{"admin", "secretpassword"},
			mustContain: []string{"***@nats-prod:4222"},
		},
		{
			name:        "username only stripped",
			input:       "nats://admin@nats-prod:4222",
			mustNotHave: []string{"admin"},
			mustContain: []string{"***@nats-prod:4222"},
		},
		{
			name:         "tls scheme preserved",
			input:        "tls://user:pw@host:4222",
			mustNotHave:  []string{"user", "pw"},
			mustContain:  []string{"tls://", "***@host:4222"},
			useExactOnly: false,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			got := redactNatsURL(tc.input)
			if tc.useExactOnly {
				if got != tc.exactMatch {
					t.Errorf("redactNatsURL(%q) = %q, want %q", tc.input, got, tc.exactMatch)
				}
				return
			}
			for _, bad := range tc.mustNotHave {
				if strings.Contains(got, bad) {
					t.Errorf("redactNatsURL(%q) = %q, must not contain %q", tc.input, got, bad)
				}
			}
			for _, good := range tc.mustContain {
				if !strings.Contains(got, good) {
					t.Errorf("redactNatsURL(%q) = %q, must contain %q", tc.input, got, good)
				}
			}
		})
	}
}

func TestRunWorkerStartRejectsBadInput(t *testing.T) {
	// Can't easily test runWorkerStart directly because of cobra + global
	// flag state, but the helpers above cover the validation paths that
	// runWorkerStart calls into before invoking execDocker.
	t.Run("validators_cover_runWorkerStart_preconditions", func(t *testing.T) {
		t.Parallel()
		if err := validateNatsURL(""); err == nil {
			t.Error("expected empty URL to be rejected")
		}
		if err := validateContainerName("bad;name"); err == nil {
			t.Error("expected unsafe container name to be rejected")
		}
	})
}
