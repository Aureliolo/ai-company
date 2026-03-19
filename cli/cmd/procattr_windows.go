package cmd

import "syscall"

// windowsDetachedProcAttr returns SysProcAttr that detaches the child
// process so it survives after the parent exits.
func windowsDetachedProcAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP,
	}
}
