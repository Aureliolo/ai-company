package cmd

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/verify"
)

func TestSandboxImageRef(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name  string
		state config.State
		want  string
	}{
		{
			name: "tag fallback when no verified digest",
			state: config.State{
				ImageTag: "latest",
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox:latest",
		},
		{
			name: "tag fallback when digest map missing sandbox key",
			state: config.State{
				ImageTag: "v0.6.5",
				VerifiedDigests: map[string]string{
					"backend": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox:v0.6.5",
		},
		{
			name: "digest pin when verified digest present",
			state: config.State{
				ImageTag: "latest",
				VerifiedDigests: map[string]string{
					"sandbox": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
		},
		{
			name: "empty digest falls back to tag",
			state: config.State{
				ImageTag: "latest",
				VerifiedDigests: map[string]string{
					"sandbox": "",
				},
			},
			want: "ghcr.io/aureliolo/synthorg-sandbox:latest",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			got := verify.FormatImageRef("sandbox", tc.state.ImageTag, tc.state.VerifiedDigests["sandbox"])
			if got != tc.want {
				t.Errorf("sandboxImageRef = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestDockerRunQuiet(t *testing.T) {
	t.Parallel()

	// Use a cross-platform no-op command (`go version`) as a stand-in for
	// the docker binary so the test stays hermetic without a real Docker
	// daemon. info.DockerPath points at any resolvable executable.
	info := docker.Info{DockerPath: "go"}

	t.Run("command succeeds returns nil", func(t *testing.T) {
		t.Parallel()
		ctx := context.Background()
		if err := dockerRunQuiet(ctx, info, "version"); err != nil {
			t.Errorf("expected nil error from successful invocation, got %v", err)
		}
	})

	t.Run("command failure wraps sanitized stderr", func(t *testing.T) {
		t.Parallel()
		ctx := context.Background()
		err := dockerRunQuiet(ctx, info, "not-a-real-subcommand-xyzzy")
		if err == nil {
			t.Fatal("expected error from bad subcommand")
		}
		msg := err.Error()
		// Output should be present and printable (sanitizer strips control bytes).
		for _, r := range msg {
			if r < 0x20 && r != '\n' {
				t.Errorf("error message contains control byte 0x%02x: %q", r, msg)
			}
		}
	})

	t.Run("empty DockerPath falls back to PATH lookup", func(t *testing.T) {
		t.Parallel()
		ctx := context.Background()
		// Info with empty DockerPath -- the function must fall back to the
		// literal "docker". We do not assume docker is installed on the
		// test host, so the expected outcomes are (1) exec.LookPath fails
		// because no docker binary is present, or (2) docker rejects the
		// bogus arg with a non-zero exit. Either proves the fallback path
		// ran; a nil error would indicate the fallback is broken.
		emptyInfo := docker.Info{DockerPath: ""}
		err := dockerRunQuiet(ctx, emptyInfo, "__this_arg_is_not_valid__")
		if err == nil {
			t.Error("expected error from empty DockerPath fallback with bogus arg")
		}
	})

	t.Run("cancelled context propagates", func(t *testing.T) {
		t.Parallel()
		ctx, cancel := context.WithCancel(context.Background())
		cancel()
		err := dockerRunQuiet(ctx, info, "version")
		if err == nil {
			t.Fatal("expected error when context is already cancelled")
		}
		// exec.CommandContext surfaces cancellation via errors.Is when the
		// child process is killed before writing output; accept either the
		// direct ctx.Err() or an exec error string that references the
		// cancellation.
		if !errors.Is(err, context.Canceled) && !strings.Contains(err.Error(), "killed") && !strings.Contains(err.Error(), "canceled") {
			t.Errorf("expected cancellation-related error, got: %v", err)
		}
	})
}

func TestDockerPullWithRetryBackoff(t *testing.T) {
	// attempts + baseDelay are now function parameters (HYG-2): the
	// caller in start.go threads them from the resolved
	// config.Tunables, and tests supply their own deterministic
	// values without mutating package-level state.
	const (
		testAttempts  = 3
		testBaseDelay = 5 * time.Millisecond
	)

	// Force failure by pointing DockerPath at a non-existent binary.
	info := docker.Info{DockerPath: "/nonexistent/docker-binary-that-does-not-exist"}

	start := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	err := dockerPullWithRetry(ctx, info, "fake-image:latest", testAttempts, testBaseDelay)
	elapsed := time.Since(start)

	if err == nil {
		t.Fatal("expected error when docker binary is missing")
	}
	// With attempts=3 and base backoff 5ms, expected waits are ~5ms + ~10ms = ~15ms.
	// Allow generous slack for scheduling.
	if elapsed < 10*time.Millisecond {
		t.Errorf("retry backoff not applied: elapsed=%v, expected at least 10ms", elapsed)
	}
}
