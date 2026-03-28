package cmd

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

var (
	stopTimeout string
	stopVolumes bool
)

var stopCmd = &cobra.Command{
	Use:   "stop",
	Short: "Stop the SynthOrg stack",
	RunE:  runStop,
}

func init() {
	stopCmd.Flags().StringVarP(&stopTimeout, "timeout", "t", "", "graceful shutdown timeout (e.g. 30s, 1m)")
	stopCmd.Flags().BoolVar(&stopVolumes, "volumes", false, "also remove named volumes")
	rootCmd.AddCommand(stopCmd)
}

func runStop(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	opts := GetGlobalOpts(ctx)

	state, err := config.Load(opts.DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("compose.yml not found in %s -- run 'synthorg init' first", safeDir)
	}
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}

	downArgs := []string{"down"}
	if stopTimeout != "" {
		dur, parseErr := time.ParseDuration(stopTimeout)
		if parseErr != nil {
			return fmt.Errorf("invalid --timeout %q: %w", stopTimeout, parseErr)
		}
		downArgs = append(downArgs, "--timeout", strconv.Itoa(int(dur.Seconds())))
	}
	if stopVolumes {
		downArgs = append(downArgs, "--volumes")
	}

	sp := out.StartSpinner("Stopping containers...")
	if err := composeRunQuiet(ctx, info, safeDir, downArgs...); err != nil {
		sp.Error("Failed to stop containers")
		return fmt.Errorf("stopping containers: %w", err)
	}
	sp.Success("SynthOrg stopped")

	return nil
}
