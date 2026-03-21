package cmd

import (
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/version"
	"github.com/spf13/cobra"
)

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print CLI version and build info",
	Run: func(cmd *cobra.Command, args []string) {
		out := ui.NewUI(cmd.OutOrStdout())
		out.Logo(version.Version)
		out.KeyValue("Commit", version.Commit)
		out.KeyValue("Built", version.Date)
	},
}

func init() {
	rootCmd.AddCommand(versionCmd)
}
