package cmd

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"strconv"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

const (
	defaultWorkerCount = 4
	defaultNatsURL     = "nats://nats:4222"
	defaultStreamPfx   = "SYNTHORG"
)

var (
	workerStartCount        int
	workerStartNatsURL      string
	workerStartStreamPrefix string
	workerStartContainer    string
)

var workerStartCmd = &cobra.Command{
	Use:   "start",
	Short: "Start a pool of distributed task queue workers",
	Long: `Spawns a worker pool inside the backend container via ` + "`docker exec`" + `.

Workers connect to NATS JetStream, pull task claims from the work
queue, execute the task via the agent runtime, and transition the
task back through the backend HTTP API.

Requires the distributed runtime profile to be running
(` + "`docker compose --profile distributed up`" + `). The default NATS URL targets
the in-network DNS name ` + "`nats`" + `; override with --nats-url for external setups.`,
	Example: `  synthorg worker start                               # 4 workers, default NATS URL
  synthorg worker start --workers 8                   # 8 workers
  synthorg worker start --nats-url nats://nats:4222   # explicit NATS URL
  synthorg worker start --container synthorg-backend  # explicit container name`,
	RunE: runWorkerStart,
}

func init() {
	workerStartCmd.Flags().IntVar(&workerStartCount, "workers", defaultWorkerCount,
		"number of concurrent workers in the pool (default 4)")
	workerStartCmd.Flags().StringVar(&workerStartNatsURL, "nats-url", defaultNatsURL,
		"NATS server URL reachable from inside the backend container")
	workerStartCmd.Flags().StringVar(&workerStartStreamPrefix, "stream-prefix", defaultStreamPfx,
		"JetStream stream name prefix")
	workerStartCmd.Flags().StringVar(&workerStartContainer, "container", "",
		"backend container name (default: synthorg-backend)")
	workerCmd.AddCommand(workerStartCmd)
}

func runWorkerStart(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	if workerStartCount <= 0 {
		return fmt.Errorf("--workers must be > 0, got %d", workerStartCount)
	}
	if err := validateNatsURL(workerStartNatsURL); err != nil {
		return err
	}
	if err := validateContainerName(workerStartContainer); err != nil {
		return err
	}

	container := workerStartContainer
	if container == "" {
		container = "synthorg-backend"
	}

	// Pass the NATS URL via env only. Putting `--nats-url <value>` into
	// the command argv would expose `nats://user:pass@host` to anyone
	// reading the docker process list even though the log output is
	// redacted, so the Python entry point reads `SYNTHORG_NATS_URL` and
	// the stream prefix from the environment instead. Worker count stays
	// on both surfaces so operators still see it in the banner.
	args := []string{
		"exec",
		"-e", "SYNTHORG_NATS_URL=" + workerStartNatsURL,
		"-e", "SYNTHORG_NATS_STREAM_PREFIX=" + workerStartStreamPrefix,
		"-e", "SYNTHORG_WORKER_COUNT=" + strconv.Itoa(workerStartCount),
		container,
		"python", "-m", "synthorg.workers",
		"--workers", strconv.Itoa(workerStartCount),
	}

	out.KeyValue("Workers", strconv.Itoa(workerStartCount))
	out.KeyValue("NATS URL", redactNatsURL(workerStartNatsURL))
	out.KeyValue("Stream prefix", workerStartStreamPrefix)
	out.KeyValue("Container", container)
	out.HintNextStep("Press Ctrl+C to stop workers.")

	return execDocker(cmd.Context(), args)
}

// validateNatsURL rejects obviously malformed URLs before we pass them
// to docker exec. nats-py does its own validation at connection time,
// but catching a typo up front gives a better error message and
// avoids wasted container startup.
func validateNatsURL(raw string) error {
	if raw == "" {
		return fmt.Errorf("--nats-url must not be empty")
	}
	parsed, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("invalid --nats-url %q: %w", redactNatsURL(raw), err)
	}
	switch parsed.Scheme {
	case "nats", "tls", "nats+tls":
		// ok
	default:
		return fmt.Errorf(
			"invalid --nats-url scheme %q: must be nats://, tls://, or nats+tls://",
			parsed.Scheme,
		)
	}
	if parsed.Host == "" {
		return fmt.Errorf("invalid --nats-url %q: missing host", redactNatsURL(raw))
	}
	return nil
}

// validateContainerName rejects container names that would fail
// docker's own parsing before we shell out. Docker allows
// alphanumerics, underscores, hyphens, and periods; anything else is
// a user error.
func validateContainerName(name string) error {
	if name == "" {
		// Empty means "use default" -- validated later.
		return nil
	}
	for _, r := range name {
		ok := (r >= 'a' && r <= 'z') ||
			(r >= 'A' && r <= 'Z') ||
			(r >= '0' && r <= '9') ||
			r == '_' || r == '-' || r == '.'
		if !ok {
			return fmt.Errorf(
				"invalid --container %q: must match [a-zA-Z0-9_.-]",
				name,
			)
		}
	}
	return nil
}

// redactNatsURL strips credentials from a NATS URL so the caller can
// log it safely. nats://user:pass@host:port becomes nats://***@host:port.
// Non-URL strings pass through so the user still sees something useful
// in error messages.
func redactNatsURL(raw string) string {
	parsed, err := url.Parse(raw)
	if err != nil || parsed.Host == "" {
		return raw
	}
	if parsed.User == nil {
		return raw
	}
	scheme := parsed.Scheme
	if scheme == "" {
		scheme = "nats"
	}
	rest := parsed.Path
	if parsed.RawQuery != "" {
		rest += "?" + parsed.RawQuery
	}
	return strings.TrimRight(fmt.Sprintf("%s://***@%s%s", scheme, parsed.Host, rest), "/")
}

// execDocker runs `docker <args...>` and streams output to the parent
// process. Factored out so worker_start_test.go can override it in
// unit tests.
var execDocker = func(ctx context.Context, args []string) error {
	//nolint:gosec // args are constructed from validated flags above.
	dockerCmd := exec.CommandContext(ctx, "docker", args...)
	dockerCmd.Stdout = os.Stdout
	dockerCmd.Stderr = os.Stderr
	dockerCmd.Stdin = os.Stdin
	return dockerCmd.Run()
}
