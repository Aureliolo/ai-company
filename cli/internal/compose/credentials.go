package compose

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"
)

// GeneratePassword produces a cryptographically random URL-safe password.
// The length parameter specifies the number of random bytes; the resulting
// string is base64url-encoded and therefore longer than length bytes.
func GeneratePassword(length int) (string, error) {
	if length < 16 {
		return "", fmt.Errorf("password length must be >= 16, got %d", length)
	}
	b := make([]byte, length)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("generating password: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}
