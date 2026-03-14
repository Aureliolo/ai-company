// Package version holds build-time version information injected via ldflags.
package version

// Version, Commit, and Date are set by GoReleaser at build time via ldflags.
var (
	Version = "dev"
	Commit  = "none"
	Date    = "unknown"
)
