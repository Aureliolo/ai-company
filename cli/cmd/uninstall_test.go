package cmd

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestIsInsideDir(t *testing.T) {
	// Use temp dirs for absolute-path tests (mirrors production usage).
	parentDir := t.TempDir()
	childDir := filepath.Join(parentDir, "sub", "deep")
	if err := os.MkdirAll(childDir, 0o755); err != nil {
		t.Fatal(err)
	}

	tests := []struct {
		name   string
		child  string
		parent string
		want   bool
	}{
		{
			name:   "child inside parent (absolute)",
			child:  filepath.Join(parentDir, "sub", "deep"),
			parent: parentDir,
			want:   true,
		},
		{
			name:   "child equals parent (absolute)",
			child:  parentDir,
			parent: parentDir,
			want:   true,
		},
		{
			name:   "child outside parent (absolute)",
			child:  t.TempDir(),
			parent: parentDir,
			want:   false,
		},
		{
			name:   "child is parent prefix but not subdir",
			child:  filepath.Join("a", "bc"),
			parent: filepath.Join("a", "b"),
			want:   false,
		},
	}

	// Add Windows-specific tests.
	if runtime.GOOS == "windows" {
		tests = append(tests,
			struct {
				name   string
				child  string
				parent string
				want   bool
			}{
				name:   "different drives",
				child:  `D:\foo\bar`,
				parent: `C:\foo`,
				want:   false,
			},
			struct {
				name   string
				child  string
				parent string
				want   bool
			}{
				name:   "case-insensitive match on Windows",
				child:  filepath.Join(parentDir, "Sub", "Deep"),
				parent: parentDir,
				want:   true,
			},
		)
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
	//       keep.txt   <- excluded
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

	// Create the excluded file outside root so the test matches its intent.
	outsideDir := t.TempDir()
	outside := filepath.Join(outsideDir, "outside.txt")
	if err := os.WriteFile(outside, []byte("keep"), 0o644); err != nil {
		t.Fatal(err)
	}

	if err := removeAllExcept(root, outside); err != nil {
		t.Fatalf("removeAllExcept: %v", err)
	}

	if _, err := os.Stat(f); err == nil {
		t.Error("expected file.txt to be removed when excluded is outside root")
	}

	// Outside file must be untouched.
	if _, err := os.Stat(outside); err != nil {
		t.Errorf("outside.txt should not have been affected: %v", err)
	}
}

func TestRemoveAllExcept_EmptyDir(t *testing.T) {
	root := t.TempDir()
	if err := removeAllExcept(root, filepath.Join(root, "nonexistent")); err != nil {
		t.Fatalf("removeAllExcept on empty dir: %v", err)
	}
}

func TestRemoveAllExcept_CaseInsensitiveWindows(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("Windows-specific test")
	}
	root := t.TempDir()
	file := filepath.Join(root, "Keep.txt")
	if err := os.WriteFile(file, []byte("data"), 0o644); err != nil {
		t.Fatal(err)
	}
	// Pass lowercase version as excluded path.
	excluded := filepath.Join(root, "keep.txt")
	if err := removeAllExcept(root, excluded); err != nil {
		t.Fatalf("removeAllExcept: %v", err)
	}
	// File should still exist (same file on NTFS).
	if _, err := os.Stat(file); err != nil {
		t.Errorf("excluded file was removed despite case difference: %v", err)
	}
}

func TestRemoveAllExcept_PreservesRoot(t *testing.T) {
	root := t.TempDir()
	f := filepath.Join(root, "file.txt")
	if err := os.WriteFile(f, []byte("data"), 0o644); err != nil {
		t.Fatal(err)
	}

	// Excluded is outside root, so all contents are removed.
	outside := filepath.Join(t.TempDir(), "outside.txt")
	if err := os.WriteFile(outside, []byte("keep"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := removeAllExcept(root, outside); err != nil {
		t.Fatalf("removeAllExcept: %v", err)
	}

	// Root directory itself must still exist.
	info, err := os.Stat(root)
	if err != nil {
		t.Fatalf("root directory was removed: %v", err)
	}
	if !info.IsDir() {
		t.Fatal("root is no longer a directory")
	}
}
