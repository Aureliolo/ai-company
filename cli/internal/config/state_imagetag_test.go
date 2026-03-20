package config

import (
	"strings"
	"testing"
)

func TestIsValidImageTag(t *testing.T) {
	tests := []struct {
		name string
		tag  string
		want bool
	}{
		{name: "empty string", tag: "", want: false},
		{name: "latest", tag: "latest", want: true},
		{name: "starts with hyphen", tag: "-abc", want: false},
		{name: "starts with dot", tag: ".abc", want: false},
		{name: "valid semver", tag: "1.2.3", want: true},
		{name: "unicode chars", tag: "v1.\u00e9", want: false},
		{name: "128 char tag", tag: strings.Repeat("a", 128), want: true},
		{name: "129 char tag", tag: strings.Repeat("a", 129), want: false},
		{name: "mixed valid chars", tag: "a.b-c_d", want: true},
		{name: "single char", tag: "a", want: true},
		{name: "single digit", tag: "1", want: true},
		{name: "starts with underscore", tag: "_abc", want: false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IsValidImageTag(tt.tag)
			if got != tt.want {
				t.Errorf("IsValidImageTag(%q) = %v, want %v", tt.tag, got, tt.want)
			}
		})
	}
}
