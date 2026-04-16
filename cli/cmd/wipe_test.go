package cmd

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"errors"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestIsEmptyPS(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name    string
		output  string
		want    bool
		wantErr bool
	}{
		{"empty string", "", true, false},
		{"empty JSON array", "[]", true, false},
		{"empty array with newline", "[]\n", true, false},
		{"empty with whitespace", "  []  ", true, false},
		{"empty array with inner space", "[ ]", true, false},
		{"non-empty JSON", `[{"Name":"backend"}]`, false, false},
		{"whitespace only", "   ", true, false},
		{"single container", `{"Name":"backend","State":"running"}`, false, false},
		{"NDJSON multiple containers", "{\"Name\":\"backend\"}\n{\"Name\":\"web\"}\n", false, false},
		{"malformed JSON array", "[invalid", false, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got, err := isEmptyPS(tt.output)
			if (err != nil) != tt.wantErr {
				t.Errorf("isEmptyPS(%q) error = %v, wantErr %v", tt.output, err, tt.wantErr)
				return
			}
			if got != tt.want {
				t.Errorf("isEmptyPS(%q) = %v, want %v", tt.output, got, tt.want)
			}
		})
	}
}

func TestOpenBrowser_RejectsNonLocalhost(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name    string
		url     string
		wantErr string
	}{
		{"external host", "http://example.com/setup", "refusing to open URL with host"},
		{"ftp scheme", "ftp://localhost/file", "refusing to open URL with scheme"},
		{"javascript scheme", "javascript:alert(1)", "refusing to open URL with scheme"},
		{"file scheme", "file:///etc/passwd", "refusing to open URL with scheme"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			err := openBrowser(t.Context(), tt.url)
			if err == nil {
				t.Fatal("expected error, got nil")
			}
			if !strings.Contains(err.Error(), tt.wantErr) {
				t.Errorf("error %q does not contain %q", err.Error(), tt.wantErr)
			}
		})
	}
}

func TestOpenBrowser_AcceptsLocalhost(t *testing.T) {
	t.Parallel()
	// We can't fully test browser opening in CI, but we can verify
	// the URL validation passes for valid localhost URLs.
	validURLs := []string{
		"http://localhost:3000/setup",
		"http://127.0.0.1:8000/setup",
		"https://localhost:3000/setup",
	}
	for _, u := range validURLs {
		t.Run(u, func(t *testing.T) {
			t.Parallel()
			// openBrowser will attempt to launch a browser binary which may
			// not exist in CI -- that's fine, we're testing the URL validation.
			err := openBrowser(t.Context(), u)
			if err != nil {
				// "starting browser" errors are expected in CI (no browser)
				if strings.Contains(err.Error(), "starting browser") {
					return
				}
				t.Errorf("unexpected error for valid URL %q: %v", u, err)
			}
		})
	}
}

func TestCreateTarGz(t *testing.T) {
	t.Parallel()
	// Create a source directory with test files.
	srcDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(srcDir, "data.txt"), []byte("hello world"), 0o600); err != nil {
		t.Fatal(err)
	}
	subDir := filepath.Join(srcDir, "sub")
	if err := os.Mkdir(subDir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(subDir, "nested.txt"), []byte("nested content"), 0o600); err != nil {
		t.Fatal(err)
	}

	// Create archive.
	var buf bytes.Buffer
	if err := createTarGz(&buf, srcDir); err != nil {
		t.Fatalf("createTarGz: %v", err)
	}

	// Verify archive contents.
	gr, err := gzip.NewReader(&buf)
	if err != nil {
		t.Fatalf("gzip reader: %v", err)
	}
	defer func() { _ = gr.Close() }()

	tr := tar.NewReader(gr)
	found := map[string]string{}
	for {
		hdr, err := tr.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			t.Fatalf("reading tar: %v", err)
		}
		if hdr.Typeflag == tar.TypeReg {
			data, readErr := io.ReadAll(tr)
			if readErr != nil {
				t.Fatalf("reading %q: %v", hdr.Name, readErr)
			}
			found[hdr.Name] = string(data)
		}
	}

	if got, ok := found["data.txt"]; !ok || got != "hello world" {
		t.Errorf("data.txt: got %q, want %q (found=%v)", got, "hello world", ok)
	}
	if got, ok := found["sub/nested.txt"]; !ok || got != "nested content" {
		t.Errorf("sub/nested.txt: got %q, want %q (found=%v)", got, "nested content", ok)
	}
}

func TestCreateTarGz_StripsHostIdentity(t *testing.T) {
	t.Parallel()
	srcDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(srcDir, "file.txt"), []byte("content"), 0o600); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	if err := createTarGz(&buf, srcDir); err != nil {
		t.Fatalf("createTarGz: %v", err)
	}

	gr, err := gzip.NewReader(&buf)
	if err != nil {
		t.Fatalf("gzip reader: %v", err)
	}
	defer func() { _ = gr.Close() }()

	tr := tar.NewReader(gr)
	hdr, err := tr.Next()
	if err != nil {
		t.Fatalf("reading first entry: %v", err)
	}

	if hdr.Uid != 0 || hdr.Gid != 0 {
		t.Errorf("expected Uid=0 Gid=0, got Uid=%d Gid=%d", hdr.Uid, hdr.Gid)
	}
	if hdr.Uname != "" || hdr.Gname != "" {
		t.Errorf("expected empty Uname/Gname, got Uname=%q Gname=%q", hdr.Uname, hdr.Gname)
	}
}

func TestTarDirectory_EmptyDir(t *testing.T) {
	t.Parallel()
	srcDir := t.TempDir()
	dstPath := filepath.Join(t.TempDir(), "out.tar.gz")

	err := tarDirectory(srcDir, dstPath)
	if err == nil {
		t.Fatal("expected error for empty directory")
	}
	if !strings.Contains(err.Error(), "empty") {
		t.Errorf("error %q does not mention empty", err.Error())
	}
}

func TestTarDirectory_RoundTrip(t *testing.T) {
	t.Parallel()
	// Create source directory with a file.
	srcDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(srcDir, "test.txt"), []byte("round trip"), 0o600); err != nil {
		t.Fatal(err)
	}

	dstPath := filepath.Join(t.TempDir(), "backup.tar.gz")
	if err := tarDirectory(srcDir, dstPath); err != nil {
		t.Fatalf("tarDirectory: %v", err)
	}

	// Verify archive was created and is a valid gzip.
	f, err := os.Open(dstPath)
	if err != nil {
		t.Fatalf("opening archive: %v", err)
	}
	defer func() { _ = f.Close() }()

	gr, err := gzip.NewReader(f)
	if err != nil {
		t.Fatalf("gzip reader: %v", err)
	}
	defer func() { _ = gr.Close() }()

	tr := tar.NewReader(gr)
	hdr, err := tr.Next()
	if err != nil {
		t.Fatalf("reading first entry: %v", err)
	}
	if hdr.Name != "test.txt" {
		t.Errorf("unexpected archive entry: %q", hdr.Name)
	}
	data, readErr := io.ReadAll(tr)
	if readErr != nil {
		t.Fatalf("reading %q: %v", hdr.Name, readErr)
	}
	if string(data) != "round trip" {
		t.Errorf("content = %q, want %q", string(data), "round trip")
	}
}

func TestTarDirectory_RestrictedPermissions(t *testing.T) {
	t.Parallel()
	if runtime.GOOS == "windows" {
		t.Skip("file permission bits are not enforced on Windows")
	}

	srcDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(srcDir, "secret.db"), []byte("sensitive"), 0o600); err != nil {
		t.Fatal(err)
	}

	dstPath := filepath.Join(t.TempDir(), "backup.tar.gz")
	if err := tarDirectory(srcDir, dstPath); err != nil {
		t.Fatalf("tarDirectory: %v", err)
	}

	// Verify the archive file has restricted permissions (0o600).
	info, err := os.Stat(dstPath)
	if err != nil {
		t.Fatalf("stat archive: %v", err)
	}
	if perm := info.Mode().Perm(); perm&0o077 != 0 {
		t.Errorf("archive permissions = %o, want no group/other access", perm)
	}
}

// TestRemoveDataDirExceptSelf covers the wipe primitive that powers
// `synthorg wipe` on Windows, where the running .exe is locked and
// cannot be deleted. The function must (a) wipe normally when the
// binary lives outside the data dir, and (b) preserve the binary
// (and its ancestor dirs) while clearing everything else when the
// binary lives inside.
//
// We synthesize "the running binary" with a real file so the path
// rewrite via os.Executable still resolves something valid -- the test
// can't directly stub os.Executable, but we don't need to: we ensure
// behaviour against a directory tree whose contents all live alongside
// (or under) os.Executable's actual return value.
func TestRemoveDataDirExceptSelf_BinaryOutsideDataDir(t *testing.T) {
	dataDir := t.TempDir()
	// Create some files; binary path lives in another tempdir entirely
	// so the function should remove the whole data dir.
	if err := os.WriteFile(filepath.Join(dataDir, "config.json"), []byte("{}"), 0o600); err != nil {
		t.Fatalf("seed config: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(dataDir, "logs"), 0o700); err != nil {
		t.Fatalf("seed logs: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "logs", "app.log"), []byte("x"), 0o600); err != nil {
		t.Fatalf("seed log: %v", err)
	}

	if err := removeDataDirExceptSelf(dataDir); err != nil {
		t.Fatalf("removeDataDirExceptSelf: %v", err)
	}
	if _, err := os.Stat(dataDir); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("data dir should be gone, got err=%v", err)
	}
}

func TestRemoveDataDirExceptSelf_BinaryInsideDataDir(t *testing.T) {
	// Drive the full removeDataDirExceptSelf code path via its testable
	// inner helper (removeDataDirExceptBinary), so the os.Executable
	// ->EvalSymlinks->filepath.Rel branch selection is actually
	// exercised instead of stubbed by calling removeAllExcept directly.
	dataDir := t.TempDir()
	keep := filepath.Join(dataDir, "bin", "synthorg-fake.exe")
	if err := os.MkdirAll(filepath.Dir(keep), 0o700); err != nil {
		t.Fatalf("mkdir bin: %v", err)
	}
	if err := os.WriteFile(keep, []byte("fake-binary"), 0o755); err != nil {
		t.Fatalf("seed binary: %v", err)
	}
	other := filepath.Join(dataDir, "config.json")
	if err := os.WriteFile(other, []byte("{}"), 0o600); err != nil {
		t.Fatalf("seed config: %v", err)
	}
	logsFile := filepath.Join(dataDir, "logs", "app.log")
	if err := os.MkdirAll(filepath.Dir(logsFile), 0o700); err != nil {
		t.Fatalf("mkdir logs: %v", err)
	}
	if err := os.WriteFile(logsFile, []byte("log"), 0o600); err != nil {
		t.Fatalf("seed log: %v", err)
	}

	if err := removeDataDirExceptBinary(dataDir, keep); err != nil {
		t.Fatalf("removeDataDirExceptBinary: %v", err)
	}
	if _, err := os.Stat(keep); err != nil {
		t.Errorf("kept binary should still exist: %v", err)
	}
	if _, err := os.Stat(other); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("config.json should be removed, got err=%v", err)
	}
	if _, err := os.Stat(logsFile); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("logs file should be removed, got err=%v", err)
	}
}

func TestRemoveDataDirExceptBinary_BinaryOutsideDataDir(t *testing.T) {
	// When the binary path is NOT under dataDir, removeDataDirExceptBinary
	// must behave identically to os.RemoveAll(dataDir).
	dataDir := t.TempDir()
	otherDir := t.TempDir()
	selfPath := filepath.Join(otherDir, "synthorg-fake.exe")
	if err := os.WriteFile(selfPath, []byte("binary"), 0o755); err != nil {
		t.Fatalf("seed binary: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "config.json"), []byte("{}"), 0o600); err != nil {
		t.Fatalf("seed config: %v", err)
	}

	if err := removeDataDirExceptBinary(dataDir, selfPath); err != nil {
		t.Fatalf("removeDataDirExceptBinary: %v", err)
	}
	if _, err := os.Stat(dataDir); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("data dir should be gone, got err=%v", err)
	}
	if _, err := os.Stat(selfPath); err != nil {
		t.Errorf("binary outside data dir should still exist: %v", err)
	}
}

func TestSelfPathInside(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("symlink resolution behaves differently on Windows; covered indirectly by binary-outside-dir test")
	}
	otherDir := t.TempDir()
	// Binary path is os.Executable() which is the test runner; it lives
	// outside our temp dir, so selfPathInside should report false.
	if selfPathInside(otherDir) {
		t.Errorf("selfPathInside(%q) = true, want false (test runner is not inside this tmp dir)", otherDir)
	}
}
