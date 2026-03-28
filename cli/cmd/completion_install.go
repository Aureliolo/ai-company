package cmd

import (
	"fmt"

	"github.com/Aureliolo/synthorg/cli/internal/completion"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

var completionInstallCmd = &cobra.Command{
	Use:   "completion-install",
	Short: "Install shell completions for the current shell",
	Long: `Detects your shell and installs tab-completion for synthorg commands.

Supported shells: bash, zsh, fish, powershell.

This is idempotent -- running it again will not duplicate the setup.
To generate raw completion scripts without installing, use 'synthorg completion [shell]'.`,
	Example: `  synthorg completion-install  # detect shell and install completions`,
	RunE:    runCompletionInstall,
}

func init() {
	completionInstallCmd.GroupID = "diagnostics"
	rootCmd.AddCommand(completionInstallCmd)
}

func runCompletionInstall(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	shell := completion.DetectShell()
	if shell == completion.Unknown {
		return fmt.Errorf("could not detect shell; use 'synthorg completion [bash|zsh|fish|powershell]' and install manually")
	}

	out.Step(fmt.Sprintf("Detected shell: %s", shell))

	res, err := completion.Install(cmd.Context(), rootCmd, shell)
	if err != nil {
		return fmt.Errorf("installing completions: %w", err)
	}

	if res.AlreadyInstalled {
		out.Success("Completions already installed")
		return nil
	}

	out.Success(fmt.Sprintf("Completions installed to %s", res.ProfilePath))
	out.HintNextStep("Restart your shell to activate completions")
	return nil
}
