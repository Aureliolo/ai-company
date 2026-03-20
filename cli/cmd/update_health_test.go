package cmd

import (
	"strings"
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/config"
)

func TestImageRefForService(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name  string
		svc   string
		state config.State
		want  string
	}{
		{
			name: "digest pinned backend",
			svc:  "backend",
			state: config.State{
				ImageTag: "0.4.1",
				VerifiedDigests: map[string]string{
					"backend": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-backend@sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
		},
		{
			name: "digest pinned web",
			svc:  "web",
			state: config.State{
				ImageTag: "0.4.1",
				VerifiedDigests: map[string]string{
					"web": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-web@sha256:1111111111111111111111111111111111111111111111111111111111111111",
		},
		{
			name: "digest pinned sandbox",
			svc:  "sandbox",
			state: config.State{
				ImageTag: "0.4.1",
				VerifiedDigests: map[string]string{
					"sandbox": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox@sha256:2222222222222222222222222222222222222222222222222222222222222222",
		},
		{
			name: "tag based when no digests",
			svc:  "backend",
			state: config.State{
				ImageTag: "0.4.1",
			},
			want: "ghcr.io/aureliolo/synthorg-backend:0.4.1",
		},
		{
			name: "tag based when nil digests map",
			svc:  "web",
			state: config.State{
				ImageTag:        "0.3.5",
				VerifiedDigests: nil,
			},
			want: "ghcr.io/aureliolo/synthorg-web:0.3.5",
		},
		{
			name: "tag based when empty digests map",
			svc:  "backend",
			state: config.State{
				ImageTag:        "latest",
				VerifiedDigests: map[string]string{},
			},
			want: "ghcr.io/aureliolo/synthorg-backend:latest",
		},
		{
			name: "tag based when digest key exists but value is empty",
			svc:  "backend",
			state: config.State{
				ImageTag: "0.4.1",
				VerifiedDigests: map[string]string{
					"backend": "",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-backend:0.4.1",
		},
		{
			name: "tag based when service not in digests map",
			svc:  "sandbox",
			state: config.State{
				ImageTag: "0.4.1",
				VerifiedDigests: map[string]string{
					"backend": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
					"web":     "sha256:1111111111111111111111111111111111111111111111111111111111111111",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox:0.4.1",
		},
		{
			name: "all services with digests - backend",
			svc:  "backend",
			state: config.State{
				ImageTag: "0.4.1",
				VerifiedDigests: map[string]string{
					"backend": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
					"web":     "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
					"sandbox": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-backend@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		},
		{
			// Degenerate case: empty ImageTag produces a malformed ref.
			// Not reachable in production -- detectInstallationIssues
			// guards with state.ImageTag != "" before calling
			// detectMissingImages. Kept for completeness.
			name: "empty image tag produces colon-only ref when no digest",
			svc:  "backend",
			state: config.State{
				ImageTag: "",
			},
			want: "ghcr.io/aureliolo/synthorg-backend:",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := imageRefForService(tt.svc, tt.state)
			if got != tt.want {
				t.Errorf("imageRefForService(%q, ...) = %q, want %q", tt.svc, got, tt.want)
			}
		})
	}
}

func FuzzImageRefForService(f *testing.F) {
	f.Add("backend", "0.4.1", "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890")
	f.Add("web", "0.4.1", "")
	f.Add("sandbox", "latest", "")
	f.Add("backend", "", "")

	f.Fuzz(func(t *testing.T, svc, tag, digest string) {
		state := config.State{ImageTag: tag}
		if digest != "" {
			state.VerifiedDigests = map[string]string{svc: digest}
		}
		got := imageRefForService(svc, state)

		// Invariant: result always starts with the repo prefix + service name.
		wantPrefix := "ghcr.io/aureliolo/synthorg-" + svc
		if !strings.HasPrefix(got, wantPrefix) {
			t.Errorf("imageRefForService(%q, ...) = %q, missing prefix %q", svc, got, wantPrefix)
		}

		// Invariant: result contains either "@" (digest) or ":" (tag) separator.
		rest := got[len(wantPrefix):]
		if !strings.HasPrefix(rest, "@") && !strings.HasPrefix(rest, ":") {
			t.Errorf("imageRefForService(%q, ...) = %q, no @ or : separator after prefix", svc, got)
		}

		// Invariant: digest path chosen only when digest is non-empty.
		if digest != "" && !strings.Contains(got, "@") {
			t.Errorf("imageRefForService(%q, ...) = %q, expected @ for non-empty digest", svc, got)
		}
	})
}
