// Package main is the entry point for the SynthOrg CLI.
package main

import (
	"errors"
	"os"

	"github.com/Aureliolo/synthorg/cli/cmd"
)

func main() {
	if err := cmd.Execute(); err != nil {
		// Propagate the child's exit code when re-exec'd binary fails.
		if code, ok := cmd.ChildExitCode(err); ok {
			os.Exit(code)
		}
		// Propagate typed exit codes from commands.
		var exitErr *cmd.ExitError
		if errors.As(err, &exitErr) {
			os.Exit(exitErr.Code)
		}
		os.Exit(1)
	}
}
