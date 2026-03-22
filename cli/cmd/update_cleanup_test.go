package cmd

import (
	"math"
	"strings"
	"testing"
)

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

func FuzzIsValidDockerID(f *testing.F) {
	f.Add("abcdef123456")
	f.Add("ABCDEF123456")
	f.Add("")
	f.Add("abcdef12345g")
	f.Add("abcdef 12345")
	f.Add("abcdef1234567")
	f.Fuzz(func(t *testing.T, s string) {
		result := isValidDockerID(s)
		// Invariant: true implies exactly 12 hex characters.
		if result && (len(s) != 12 || !isAllHex(s)) {
			t.Errorf("isValidDockerID(%q) = true but len=%d isAllHex=%v",
				s, len(s), isAllHex(s))
		}
	})
}

func TestParseDockerSize(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		s    string
		want float64
	}{
		{"megabytes", "646MB", 646e6},
		{"megabytes with decimal", "85.8MB", 85.8e6},
		{"gigabytes", "1.2GB", 1.2e9},
		{"terabytes", "2.5TB", 2.5e12},
		{"kilobytes lowercase", "512kB", 512e3},
		{"kilobytes uppercase", "512KB", 512e3},
		{"bytes", "100B", 100},
		{"empty", "", 0},
		{"no unit", "123", 0},
		{"invalid", "fooMB", 0},
		{"with comma", "1,024MB", 1024e6},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := parseDockerSize(tt.s)
			// Allow small floating point tolerance.
			diff := got - tt.want
			if diff < 0 {
				diff = -diff
			}
			if diff > 1 { // 1 byte tolerance
				t.Errorf("parseDockerSize(%q) = %v, want %v", tt.s, got, tt.want)
			}
		})
	}
}

func TestFormatBytes(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		b    float64
		want string
	}{
		{"terabytes", 2.5e12, "2.5 TB"},
		{"gigabytes", 1.2e9, "1.2 GB"},
		{"megabytes", 646e6, "646.0 MB"},
		{"kilobytes", 512e3, "512.0 kB"},
		{"bytes", 100, "100 B"},
		{"zero", 0, "0 B"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := formatBytes(tt.b)
			if got != tt.want {
				t.Errorf("formatBytes(%v) = %q, want %q", tt.b, got, tt.want)
			}
		})
	}
}

func TestBuildImageDisplay(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name   string
		repo   string
		tag    string
		digest string
		size   string
		id     string
		wantIn string // substring that should appear
	}{
		{
			"with tag",
			"ghcr.io/aureliolo/synthorg-backend", "0.4.3", "sha256:abc123", "646MB", "abc123def456",
			"synthorg-backend:0.4.3",
		},
		{
			"no tag, has digest",
			"ghcr.io/aureliolo/synthorg-web", "<none>", "sha256:abcdef1234567890abcdef", "85.8MB", "abcdef123456",
			"synthorg-web@abcdef1234567890",
		},
		{
			"no tag, no digest, shows id",
			"ghcr.io/aureliolo/synthorg-sandbox", "<none>", "<none>", "514MB", "deadbeef1234",
			"deadbeef1234",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := buildImageDisplay(tt.repo, tt.tag, tt.digest, tt.size, tt.id)
			if got == "" {
				t.Fatal("buildImageDisplay returned empty string")
			}
			if !strings.Contains(got, tt.wantIn) {
				t.Errorf("display %q missing label %q", got, tt.wantIn)
			}
			if !strings.Contains(got, tt.size) {
				t.Errorf("display %q missing size %q", got, tt.size)
			}
		})
	}
}

func TestMergeKeepIDs(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		current  map[string]bool
		previous map[string]bool
		wantLen  int
	}{
		{
			"nil both",
			nil,
			nil,
			0,
		},
		{
			"current only",
			map[string]bool{"aaa": true, "bbb": true},
			nil,
			2,
		},
		{
			"previous only",
			nil,
			map[string]bool{"ccc": true, "ddd": true},
			2,
		},
		{
			"current and previous merged",
			map[string]bool{"aaa": true, "bbb": true},
			map[string]bool{"ccc": true, "ddd": true},
			4,
		},
		{
			"overlapping IDs deduplicated",
			map[string]bool{"aaa": true, "bbb": true},
			map[string]bool{"aaa": true, "ccc": true},
			3,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := mergeKeepIDs(tt.current, tt.previous)
			if len(got) != tt.wantLen {
				t.Errorf("len = %d, want %d", len(got), tt.wantLen)
			}
			// Verify all inputs are in the result.
			for id := range tt.current {
				if !got[id] {
					t.Errorf("current ID %q missing from result", id)
				}
			}
			for id := range tt.previous {
				if !got[id] {
					t.Errorf("previous ID %q missing from result", id)
				}
			}
		})
	}
}

func FuzzMergeKeepIDs(f *testing.F) {
	f.Add("aaa,bbb", "bbb,ccc")
	f.Add("", "")
	f.Add("x", "")
	f.Add("", "y")
	f.Fuzz(func(t *testing.T, currentCSV, previousCSV string) {
		toMap := func(csv string) map[string]bool {
			m := map[string]bool{}
			for _, p := range strings.Split(csv, ",") {
				p = strings.TrimSpace(p)
				if p != "" {
					m[p] = true
				}
			}
			return m
		}
		current := toMap(currentCSV)
		previous := toMap(previousCSV)
		got := mergeKeepIDs(current, previous)

		// Build expected union.
		expected := make(map[string]bool)
		for id := range current {
			expected[id] = true
		}
		for id := range previous {
			expected[id] = true
		}

		// Assert exact union: correct size, all expected present, no extras.
		if len(got) != len(expected) {
			t.Fatalf("len(got) = %d, want %d", len(got), len(expected))
		}
		for id := range expected {
			if !got[id] {
				t.Fatalf("missing expected id %q", id)
			}
		}
		for id := range got {
			if !expected[id] {
				t.Fatalf("unexpected extra id %q", id)
			}
		}
	})
}

func FuzzIsAllHex(f *testing.F) {
	f.Add("0123456789abcdef")
	f.Add("0123456789ABCDEF")
	f.Add("")
	f.Add("g")
	f.Add("abc!def")
	f.Add("abc def")
	f.Fuzz(func(t *testing.T, s string) {
		result := isAllHex(s)
		// Cross-check: isAllHex && len==12 must imply isValidDockerID.
		if result && len(s) == 12 && !isValidDockerID(s) {
			t.Errorf("isAllHex(%q)=true, len=12, but isValidDockerID=false", s)
		}
	})
}

func FuzzParseDockerSize(f *testing.F) {
	f.Add("646MB")
	f.Add("85.8MB")
	f.Add("1.2GB")
	f.Add("2.5TB")
	f.Add("512kB")
	f.Add("512KB")
	f.Add("100B")
	f.Add("1,024MB")
	f.Add("")
	f.Add("fooMB")
	f.Add("123")
	f.Add("NaNMB")
	f.Add("InfGB")
	f.Add("-InfTB")
	f.Fuzz(func(t *testing.T, s string) {
		v := parseDockerSize(s)
		// Invariant: result must always be finite (NaN/Inf rejected).
		if math.IsNaN(v) || math.IsInf(v, 0) {
			t.Errorf("parseDockerSize(%q) = %v, want finite value", s, v)
		}
	})
}
