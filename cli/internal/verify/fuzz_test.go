package verify

import (
	"strings"
	"testing"
)

// FuzzIsValidDigest verifies that IsValidDigest never panics and that
// valid digests are a subset of strings matching the expected format.
func FuzzIsValidDigest(f *testing.F) {
	f.Add("sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
	f.Add("sha256:0000000000000000000000000000000000000000000000000000000000000000")
	f.Add("md5:abcdef1234567890abcdef1234567890")
	f.Add("")
	f.Add("sha256:short")
	f.Add("sha256:UPPERCASE")

	f.Fuzz(func(t *testing.T, digest string) {
		result := IsValidDigest(digest)
		if result {
			// If valid, must start with "sha256:" and have 71 total chars.
			if !strings.HasPrefix(digest, "sha256:") {
				t.Errorf("valid digest has unexpected prefix: %q", digest)
			}
			if len(digest) != 71 {
				t.Errorf("valid digest has unexpected length %d: %q", len(digest), digest)
			}
		}
	})
}

// FuzzParseDigest verifies that parseDigest never panics on arbitrary input
// and that valid results have the expected structure.
func FuzzParseDigest(f *testing.F) {
	f.Add("sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
	f.Add("sha256:0000000000000000000000000000000000000000000000000000000000000000")
	f.Add("")
	f.Add("no-colon")
	f.Add("sha512:abcdef")

	f.Fuzz(func(t *testing.T, digest string) {
		algo, b, err := parseDigest(digest)
		if err == nil {
			if algo != "sha256" {
				t.Errorf("parseDigest(%q) algo = %q, want sha256", digest, algo)
			}
			if len(b) == 0 {
				t.Errorf("parseDigest(%q) returned empty bytes", digest)
			}
		}
	})
}

// FuzzNewImageRef verifies that NewImageRef never panics and produces
// consistent output.
func FuzzNewImageRef(f *testing.F) {
	f.Add("backend", "0.3.0")
	f.Add("web", "latest")
	f.Add("sandbox", "v1.0.0-rc.1")
	f.Add("", "")

	f.Fuzz(func(t *testing.T, name, tag string) {
		if len(name) > 256 || len(tag) > 256 {
			return // cap input size
		}
		ref := NewImageRef(name, tag)
		if ref.Registry != RegistryHost {
			t.Errorf("Registry = %q, want %q", ref.Registry, RegistryHost)
		}
		if ref.Tag != tag {
			t.Errorf("Tag = %q, want %q", ref.Tag, tag)
		}
		// Repository must contain the image repo prefix.
		if ref.Repository != ImageRepoPrefix+name {
			t.Errorf("Repository = %q, want %q", ref.Repository, ImageRepoPrefix+name)
		}
	})
}
