//go:build windows

package config

// DetectDockerSockGID is a no-op on Windows where the Docker socket is a
// named pipe (`//./pipe/docker_engine`) rather than a Unix domain socket.
// Named pipe access is not governed by Unix group IDs, so compose
// `group_add` is not needed.
func DetectDockerSockGID(_ string) (int, bool) {
	return 0, false
}
