package cmd

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestIsInsideDir(t *testing.T) {
	tests := []struct {
		name   string
		child  string
		parent string
		want   bool
	}{
		{
			name:   "child inside parent",
			child:  filepath.Join("a", "b", "c"),
			parent: filepath.Join("a", "b"),
			want:   true,
		},
		{
			name:   "child equals parent",
			child:  filepath.Join("a", "b"),
			parent: filepath.Join("a", "b"),
			want:   true,
		},
		{
			name:   "child outside parent",
			child:  filepath.Join("x", "y"),
			parent: filepath.Join("a", "b"),
			want:   false,
		},
		{
			name:   "child is parent prefix but not subdir",
			child:  filepath.Join("a", "bc"),
			parent: filepath.Join("a", "b"),
			want:   false,
		},
	}

	// Add Windows-specific drive-letter tests.
	if runtime.GOOS == "windows" {
		tests = append(tests, struct {
			name   string
			child  string
			parent string
			want   bool
		}{
			name:   "different drives",
			child:  `D:\foo\bar`,
			parent: `C:\foo`,
			want:   false,
		})
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := isInsideDir(tt.child, tt.parent)
			if got != tt.want {
				t.Errorf("isInsideDir(%q, %q) = %v, want %v", tt.child, tt.parent, got, tt.want)
			}
		})
	}
}

func TestRemoveAllExcept_RemovesEverythingElse(t *testing.T) {
	root := t.TempDir()

	// Build a directory tree:
	//   root/
	//     a.txt
	//     sub/
	//       b.txt
	//       keep.txt   ← excluded
	//       deep/
	//         c.txt
	sub := filepath.Join(root, "sub")
	deep := filepath.Join(sub, "deep")
	if err := os.MkdirAll(deep, 0o755); err != nil {
		t.Fatal(err)
	}
	for _, f := range []string{
		filepath.Join(root, "a.txt"),
		filepath.Join(sub, "b.txt"),
		filepath.Join(sub, "keep.txt"),
		filepath.Join(deep, "c.txt"),
	} {
		if err := os.WriteFile(f, []byte("data"), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	excluded := filepath.Join(sub, "keep.txt")
	if err := removeAllExcept(root, excluded); err != nil {
		t.Fatalf("removeAllExcept: %v", err)
	}

	// Excluded file must still exist.
	if _, err := os.Stat(excluded); err != nil {
		t.Errorf("excluded file was removed: %v", err)
	}

	// Other files must be gone.
	for _, f := range []string{
		filepath.Join(root, "a.txt"),
		filepath.Join(sub, "b.txt"),
		filepath.Join(deep, "c.txt"),
	} {
		if _, err := os.Stat(f); err == nil {
			t.Errorf("expected %s to be removed, but it still exists", f)
		}
	}

	// deep/ directory must be gone (was empty after c.txt removed).
	if _, err := os.Stat(deep); err == nil {
		t.Error("expected deep/ directory to be removed")
	}

	// sub/ must still exist (contains keep.txt).
	if _, err := os.Stat(sub); err != nil {
		t.Errorf("sub/ should still exist (contains excluded file): %v", err)
	}
}

func TestRemoveAllExcept_ExcludeOutsideRoot(t *testing.T) {
	root := t.TempDir()

	// Create a file inside root.
	f := filepath.Join(root, "file.txt")
	if err := os.WriteFile(f, []byte("data"), 0o644); err != nil {
		t.Fatal(err)
	}

	// Exclude a file outside root — everything in root should be removed.
	outside := filepath.Join(t.TempDir(), "outside.txt")
	if err := removeAllExcept(root, outside); err != nil {
		t.Fatalf("removeAllExcept: %v", err)
	}

	if _, err := os.Stat(f); err == nil {
		t.Error("expected file.txt to be removed when excluded is outside root")
	}
}

func TestRemoveAllExcept_EmptyDir(t *testing.T) {
	root := t.TempDir()
	if err := removeAllExcept(root, filepath.Join(root, "nonexistent")); err != nil {
		t.Fatalf("removeAllExcept on empty dir: %v", err)
	}
}
