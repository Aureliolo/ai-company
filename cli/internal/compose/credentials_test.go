package compose

import (
	"strings"
	"testing"
)

func TestGeneratePasswordLength(t *testing.T) {
	pw, err := GeneratePassword(32)
	if err != nil {
		t.Fatalf("GeneratePassword(32) error: %v", err)
	}
	// 32 bytes -> 43 chars in base64url (no padding)
	if len(pw) != 43 {
		t.Errorf("password length = %d, want 43 (32 bytes base64url)", len(pw))
	}
}

func TestGeneratePasswordUniqueness(t *testing.T) {
	pw1, err := GeneratePassword(32)
	if err != nil {
		t.Fatal(err)
	}
	pw2, err := GeneratePassword(32)
	if err != nil {
		t.Fatal(err)
	}
	if pw1 == pw2 {
		t.Error("two calls produced identical passwords")
	}
}

func TestGeneratePasswordURLSafe(t *testing.T) {
	pw, err := GeneratePassword(32)
	if err != nil {
		t.Fatal(err)
	}
	// base64url uses A-Z, a-z, 0-9, -, _
	for _, c := range pw {
		isUpper := c >= 'A' && c <= 'Z'
		isLower := c >= 'a' && c <= 'z'
		isDigit := c >= '0' && c <= '9'
		if !isUpper && !isLower && !isDigit && c != '-' && c != '_' {
			t.Errorf("non-URL-safe character %q in password", c)
		}
	}
}

func TestGeneratePasswordRejectsShort(t *testing.T) {
	_, err := GeneratePassword(8)
	if err == nil {
		t.Fatal("expected error for length < 16")
	}
	if !strings.Contains(err.Error(), "must be >= 16") {
		t.Errorf("unexpected error message: %v", err)
	}
}
