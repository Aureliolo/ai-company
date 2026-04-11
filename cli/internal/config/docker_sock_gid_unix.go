//go:build !windows

package config

import (
	"os"
	"syscall"
)

// DetectDockerSockGID returns the group ID that owns the Docker socket at
// path. The backend container must belong to this group (via compose
// `group_add`) to read/write the socket when running as a non-root user.
// Returns 0 if the socket does not exist, cannot be stat'd, or the host
// does not expose Unix file metadata.
func DetectDockerSockGID(path string) int {
	info, err := os.Stat(path)
	if err != nil {
		return 0
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return 0
	}
	return int(stat.Gid)
}
