package cmd

import (
	"strings"
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/images"
)

func TestRefForService(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name            string
		svc             string
		imageTag        string
		verifiedDigests map[string]string
		want            string
	}{
		{
			name:     "digest pinned backend",
			svc:      "backend",
			imageTag: "0.4.1",
			verifiedDigests: map[string]string{
				"backend": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
			},
			want: "ghcr.io/aureliolo/synthorg-backend@sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
		},
		{
			name:     "digest pinned web",
			svc:      "web",
			imageTag: "0.4.1",
			verifiedDigests: map[string]string{
				"web": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
			},
			want: "ghcr.io/aureliolo/synthorg-web@sha256:1111111111111111111111111111111111111111111111111111111111111111",
		},
		{
			name:     "digest pinned sandbox",
			svc:      "sandbox",
			imageTag: "0.4.1",
			verifiedDigests: map[string]string{
				"sandbox": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox@sha256:2222222222222222222222222222222222222222222222222222222222222222",
		},
		{
			name:     "tag based when no digests",
			svc:      "backend",
			imageTag: "0.4.1",
			want:     "ghcr.io/aureliolo/synthorg-backend:0.4.1",
		},
		{
			name:            "tag based when nil digests map",
			svc:             "web",
			imageTag:        "0.3.5",
			verifiedDigests: nil,
			want:            "ghcr.io/aureliolo/synthorg-web:0.3.5",
		},
		{
			name:            "tag based when empty digests map",
			svc:             "backend",
			imageTag:        "latest",
			verifiedDigests: map[string]string{},
			want:            "ghcr.io/aureliolo/synthorg-backend:latest",
		},
		{
			name:     "tag based when digest key exists but value is empty",
			svc:      "backend",
			imageTag: "0.4.1",
			verifiedDigests: map[string]string{
				"backend": "",
			},
			want: "ghcr.io/aureliolo/synthorg-backend:0.4.1",
		},
		{
			name:     "tag based when service not in digests map",
			svc:      "sandbox",
			imageTag: "0.4.1",
			verifiedDigests: map[string]string{
				"backend": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
				"web":     "sha256:1111111111111111111111111111111111111111111111111111111111111111",
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox:0.4.1",
		},
		{
			name:     "all services with digests - backend",
			svc:      "backend",
			imageTag: "0.4.1",
			verifiedDigests: map[string]string{
				"backend": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
				"web":     "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
				"sandbox": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
			},
			want: "ghcr.io/aureliolo/synthorg-backend@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		},
		{
			// Degenerate case: empty ImageTag produces a malformed ref.
			// Not reachable in production -- detectInstallationIssues
			// guards with state.ImageTag != "" before calling
			// detectMissingImages. Kept for completeness.
			name:     "empty image tag produces colon-only ref when no digest",
			svc:      "backend",
			imageTag: "",
			want:     "ghcr.io/aureliolo/synthorg-backend:",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := images.RefForService(tt.svc, tt.imageTag, tt.verifiedDigests)
			if got != tt.want {
				t.Errorf("RefForService(%q, %q, ...) = %q, want %q", tt.svc, tt.imageTag, got, tt.want)
			}
		})
	}
}

func FuzzRefForService(f *testing.F) {
	f.Add("backend", "0.4.1", "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890")
	f.Add("web", "0.4.1", "")
	f.Add("sandbox", "latest", "")
	f.Add("backend", "", "")

	f.Fuzz(func(t *testing.T, svc, tag, digest string) {
		var digests map[string]string
		if digest != "" {
			digests = map[string]string{svc: digest}
		}
		got := images.RefForService(svc, tag, digests)

		// Invariant: result always starts with the repo prefix + service name.
		wantPrefix := images.RepoPrefix + svc
		if !strings.HasPrefix(got, wantPrefix) {
			t.Errorf("RefForService(%q, ...) = %q, missing prefix %q", svc, got, wantPrefix)
		}

		// Invariant: result contains either "@" (digest) or ":" (tag) separator.
		rest := got[len(wantPrefix):]
		if !strings.HasPrefix(rest, "@") && !strings.HasPrefix(rest, ":") {
			t.Errorf("RefForService(%q, ...) = %q, no @ or : separator after prefix", svc, got)
		}

		// Invariant: digest path chosen only when digest is non-empty.
		if digest != "" && !strings.Contains(got, "@") {
			t.Errorf("RefForService(%q, ...) = %q, expected @ for non-empty digest", svc, got)
		}
	})
}
