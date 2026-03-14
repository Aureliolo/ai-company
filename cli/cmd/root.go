// Package cmd defines the CLI commands for SynthOrg.
package cmd

import (
	"fmt"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/spf13/cobra"
)

var (
	dataDir string
	verbose bool
)

var rootCmd = &cobra.Command{
	Use:   "synthorg",
	Short: "SynthOrg CLI — manage your synthetic organization",
	Long: `SynthOrg CLI manages the lifecycle of your synthetic organization.

Run 'synthorg init' to set up a new installation, then 'synthorg start'
to launch the backend and web dashboard containers.`,
	SilenceUsage:  true,
	SilenceErrors: true,
}

func init() {
	rootCmd.PersistentFlags().StringVar(&dataDir, "data-dir", "", "data directory (default: platform-appropriate)")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "enable verbose output")
}

// resolveDataDir returns the effective data directory, using the flag value or
// the platform default.
func resolveDataDir() string {
	if dataDir != "" {
		return dataDir
	}
	return config.DataDir()
}

// Execute runs the root command.
func Execute() error {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(rootCmd.ErrOrStderr(), err)
		return err
	}
	return nil
}
