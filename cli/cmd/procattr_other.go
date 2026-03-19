//go:build !windows

package cmd

import "syscall"

// windowsDetachedProcAttr is a no-op stub for non-Windows platforms.
// The caller (scheduleWindowsCleanup) is only reachable on Windows,
// but the function must exist for compilation.
func windowsDetachedProcAttr() *syscall.SysProcAttr {
	return nil
}
