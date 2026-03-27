package cmd

import (
	"errors"
	"fmt"
	"testing"
)

func TestExitError(t *testing.T) {
	t.Parallel()
	inner := fmt.Errorf("something broke")
	ee := NewExitError(ExitUnhealthy, inner)

	if ee.Code != ExitUnhealthy {
		t.Errorf("Code = %d, want %d", ee.Code, ExitUnhealthy)
	}
	if ee.Error() != "something broke" {
		t.Errorf("Error() = %q, want %q", ee.Error(), "something broke")
	}
	if !errors.Is(ee, inner) {
		t.Error("Unwrap should expose the inner error")
	}
}

func TestExitErrorNilErr(t *testing.T) {
	t.Parallel()
	ee := NewExitError(ExitRuntime, nil)
	if ee.Error() != "" {
		t.Errorf("Error() = %q, want empty", ee.Error())
	}
}

func TestExitErrorAs(t *testing.T) {
	t.Parallel()
	inner := NewExitError(ExitUnreachable, fmt.Errorf("docker not found"))
	wrapped := fmt.Errorf("startup failed: %w", inner)

	var ee *ExitError
	if !errors.As(wrapped, &ee) {
		t.Fatal("errors.As should find ExitError in wrapped chain")
	}
	if ee.Code != ExitUnreachable {
		t.Errorf("Code = %d, want %d", ee.Code, ExitUnreachable)
	}
}

func TestChildExitCode(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		err      error
		wantCode int
		wantOK   bool
	}{
		{"child exit error", &ChildExitError{Code: 42}, 42, true},
		{"wrapped child exit error", fmt.Errorf("context: %w", &ChildExitError{Code: 7}), 7, true},
		{"regular error", fmt.Errorf("not a child error"), 0, false},
		{"exit error (not child)", NewExitError(3, fmt.Errorf("unhealthy")), 0, false},
		{"nil error", nil, 0, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			code, ok := ChildExitCode(tt.err)
			if ok != tt.wantOK {
				t.Errorf("ok = %v, want %v", ok, tt.wantOK)
			}
			if code != tt.wantCode {
				t.Errorf("code = %d, want %d", code, tt.wantCode)
			}
		})
	}
}
