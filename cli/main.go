// Package main is the entry point for the SynthOrg CLI.
package main

import (
	"os"

	"github.com/Aureliolo/synthorg/cli/cmd"
)

func main() {
	if err := cmd.Execute(); err != nil {
		// Propagate the child's exit code when re-exec'd binary fails,
		// instead of always exiting 1.
		if code, ok := cmd.ChildExitCode(err); ok {
			os.Exit(code)
		}
		os.Exit(1)
	}
}
