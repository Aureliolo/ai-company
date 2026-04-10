package cmd

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strconv"

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
		"backend container name (default: discover from compose)")
	workerCmd.AddCommand(workerStartCmd)
}

func runWorkerStart(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	if workerStartCount <= 0 {
		return fmt.Errorf("--workers must be > 0, got %d", workerStartCount)
	}

	container := workerStartContainer
	if container == "" {
		container = "synthorg-backend"
	}

	args := []string{
		"exec",
		"-e", "SYNTHORG_NATS_URL=" + workerStartNatsURL,
		"-e", "SYNTHORG_NATS_STREAM_PREFIX=" + workerStartStreamPrefix,
		"-e", "SYNTHORG_WORKER_COUNT=" + strconv.Itoa(workerStartCount),
		container,
		"python", "-m", "synthorg.workers",
		"--workers", strconv.Itoa(workerStartCount),
		"--nats-url", workerStartNatsURL,
		"--stream-prefix", workerStartStreamPrefix,
	}

	out.KeyValue("Workers", strconv.Itoa(workerStartCount))
	out.KeyValue("NATS URL", workerStartNatsURL)
	out.KeyValue("Stream prefix", workerStartStreamPrefix)
	out.KeyValue("Container", container)
	out.HintNextStep("Press Ctrl+C to stop workers.")

	return execDocker(cmd.Context(), args)
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
