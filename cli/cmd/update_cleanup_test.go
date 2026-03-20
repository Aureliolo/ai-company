package cmd

import "testing"

func TestIsValidDockerID(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		id   string
		want bool
	}{
		{"valid 12 hex lowercase", "abcdef123456", true},
		{"valid 12 hex uppercase", "ABCDEF123456", true},
		{"valid 12 hex mixed", "aB1cD2eF3456", true},
		{"valid all digits", "012345678901", true},
		{"too short", "abcdef12345", false},
		{"too long", "abcdef1234567", false},
		{"empty", "", false},
		{"non-hex char g", "abcdef12345g", false},
		{"non-hex char z", "abcdef12345z", false},
		{"non-hex special char", "abcdef12345!", false},
		{"spaces", "abcdef 12345", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if got := isValidDockerID(tt.id); got != tt.want {
				t.Errorf("isValidDockerID(%q) = %v, want %v", tt.id, got, tt.want)
			}
		})
	}
}

func TestIsAllHex(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		s    string
		want bool
	}{
		{"all lowercase hex", "0123456789abcdef", true},
		{"all uppercase hex", "0123456789ABCDEF", true},
		{"mixed case hex", "aAbBcCdDeEfF", true},
		{"digits only", "0123456789", true},
		{"empty string", "", true},
		{"single valid char", "a", true},
		{"single invalid char", "g", false},
		{"non-hex at start", "gabcdef", false},
		{"non-hex at end", "abcdefg", false},
		{"non-hex in middle", "abc!def", false},
		{"space", "abc def", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if got := isAllHex(tt.s); got != tt.want {
				t.Errorf("isAllHex(%q) = %v, want %v", tt.s, got, tt.want)
			}
		})
	}
}
