package cmd

import (
	"github.com/spf13/cobra"
)

// workerCmd is the parent command for distributed task queue workers.
// Subcommands (worker start, ...) delegate to the Python worker entry
// point inside the backend container.
var workerCmd = &cobra.Command{
	Use:   "worker",
	Short: "Manage distributed task queue workers",
	Long: `Distributed task queue workers pull claims from the message bus
work queue and execute tasks via the agent runtime.

Requires the distributed runtime to be enabled (communication.message_bus.backend=nats
and queue.enabled=true). See docs/design/distributed-runtime.md.`,
	GroupID: "core",
}

func init() {
	rootCmd.AddCommand(workerCmd)
}
