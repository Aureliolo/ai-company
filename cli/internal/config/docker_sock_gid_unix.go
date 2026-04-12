//go:build !windows

package config

import (
	"os"
	"syscall"
)

// DetectDockerSockGID returns the group ID that owns the Docker socket at
// path and whether detection succeeded. The backend container must belong
// to this group (via compose `group_add`) to read/write the socket when
// running as a non-root user. Returns (0, false) if the socket does not
// exist, cannot be stat'd, or the host does not expose Unix file metadata.
func DetectDockerSockGID(path string) (int, bool) {
	info, err := os.Stat(path)
	if err != nil {
		return 0, false
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return 0, false
	}
	return int(stat.Gid), true
}
