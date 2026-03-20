package docker

import (
	"testing"
)

func FuzzVersionAtLeast(f *testing.F) {
	// Seed corpus with typical version strings and edge cases.
	f.Add("27.5.1", "20.10.0")
	f.Add("20.10.0", "20.10.0")
	f.Add("19.3.0", "20.10.0")
	f.Add("v2.32.1", "2.0.0")
	f.Add("1.29.0", "2.0.0")
	f.Add("", "")
	f.Add("1", "1")
	f.Add("1.0", "1.0")
	f.Add("abc", "def")
	f.Add("1.0.0-rc1", "1.0.0")
	f.Add("v1.0.0", "v1.0.0")
	f.Add("999.999.999", "0.0.0")
	f.Add("0.0.0", "999.999.999")
	f.Add("1.2.3-beta.4", "1.2.3")

	f.Fuzz(func(t *testing.T, got, min string) {
		// Must not panic.
		result, resultErr := versionAtLeast(got, min)

		// Skip property checks if any call returned an error (invalid input).
		if resultErr != nil {
			return
		}

		// Reflexivity: versionAtLeast(x, x) must be true.
		gotGot, err := versionAtLeast(got, got)
		if err != nil {
			return
		}
		if !gotGot {
			t.Errorf("versionAtLeast(%q, %q) = false, want true (reflexivity)", got, got)
		}
		minMin, err := versionAtLeast(min, min)
		if err != nil {
			return
		}
		if !minMin {
			t.Errorf("versionAtLeast(%q, %q) = false, want true (reflexivity)", min, min)
		}

		// Total-order completeness: for any two versions, at least one of
		// versionAtLeast(got, min) or versionAtLeast(min, got) must be true.
		reverse, err := versionAtLeast(min, got)
		if err != nil {
			return
		}
		if !result && !reverse {
			t.Errorf("total-order violation: versionAtLeast(%q,%q)=false AND versionAtLeast(%q,%q)=false", got, min, min, got)
		}

		// Antisymmetry note: if both result and reverse are true, the
		// versions compare as equal despite potentially different strings.
		// Both got and min use FieldsFunc suffix-stripping, so pairs like
		// ("1.0.0-rc1", "1.0.0") normalise identically. The total-order
		// check above already covers this case (both true satisfies
		// at-least-one-true).
	})
}
