package selfupdate

import "testing"

func TestIsUpdateAvailable(t *testing.T) {
	tests := []struct {
		current string
		latest  string
		want    bool
		wantErr bool
	}{
		{"dev", "v1.0.0", true, false},
		{"v1.0.0", "v1.0.0", false, false},
		{"v1.0.0", "v1.1.0", true, false},
		{"v1.0.0", "v2.0.0", true, false},
		{"v1.0.0", "v1.0.1", true, false},
		{"v2.0.0", "v1.0.0", false, false},                  // downgrade prevented
		{"v1.1.0", "v1.0.0", false, false},                  // downgrade prevented
		{"v1.0.1", "v1.0.0", false, false},                  // downgrade prevented
		{"v1.10.0", "v1.9.0", false, false},                 // multi-digit minor downgrade
		{"v1.0.0", "99999999999999999999.0.0", false, true}, // overflow in latest
		{"99999999999999999999.0.0", "v1.0.0", false, true}, // overflow in current
	}
	for _, tt := range tests {
		t.Run(tt.current+"->"+tt.latest, func(t *testing.T) {
			got, err := isUpdateAvailable(tt.current, tt.latest)
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("isUpdateAvailable(%q, %q) unexpected error: %v", tt.current, tt.latest, err)
			}
			if got != tt.want {
				t.Errorf("isUpdateAvailable(%q, %q) = %v, want %v", tt.current, tt.latest, got, tt.want)
			}
		})
	}
}

func TestCompareSemver(t *testing.T) {
	tests := []struct {
		name    string
		a       string
		b       string
		wantCmp int // >0, 0, <0
		wantErr bool
	}{
		{"equal", "1.0.0", "1.0.0", 0, false},
		{"a greater major", "2.0.0", "1.0.0", 1, false},
		{"b greater major", "1.0.0", "2.0.0", -1, false},
		{"a greater minor", "1.2.0", "1.1.0", 1, false},
		{"a greater patch", "1.0.2", "1.0.1", 1, false},
		{"with v prefix", "v1.0.0", "v1.0.0", 0, false},
		{"pre-release suffix", "1.0.0-rc1", "1.0.0", 0, false},
		{"empty strings", "", "", 0, false},
		{"single component", "1", "2", -1, false},
		{"two components", "1.2", "1.1", 1, false},
		{"overflow version a", "99999999999999999999.0.0", "1.0.0", 0, true},
		{"overflow version b", "1.0.0", "99999999999999999999.0.0", 0, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := compareSemver(tt.a, tt.b)
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			// Check sign rather than exact value.
			switch {
			case tt.wantCmp > 0 && got <= 0:
				t.Errorf("compareSemver(%q, %q) = %d, want > 0", tt.a, tt.b, got)
			case tt.wantCmp < 0 && got >= 0:
				t.Errorf("compareSemver(%q, %q) = %d, want < 0", tt.a, tt.b, got)
			case tt.wantCmp == 0 && got != 0:
				t.Errorf("compareSemver(%q, %q) = %d, want 0", tt.a, tt.b, got)
			}
		})
	}
}
