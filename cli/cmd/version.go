package cmd

import (
	"fmt"

	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/version"
	"github.com/spf13/cobra"
)

var versionShort bool

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print CLI version and build info",
	Example: `  synthorg version          # full version info with logo
  synthorg version --short  # version number only`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if versionShort {
			_, _ = fmt.Fprintln(cmd.OutOrStdout(), version.Version)
			return nil
		}
		opts := GetGlobalOpts(cmd.Context())
		out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())
		out.Logo(version.Version)
		out.KeyValue("Commit", version.Commit)
		out.KeyValue("Built", version.Date)
		return nil
	},
}

func init() {
	versionCmd.Flags().BoolVar(&versionShort, "short", false, "print version number only")
	versionCmd.GroupID = "diagnostics"
	rootCmd.AddCommand(versionCmd)
}
