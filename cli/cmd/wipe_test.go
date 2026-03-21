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
		name   string
		output string
		want   bool
	}{
		{"empty string", "", true},
		{"empty JSON array", "[]", true},
		{"empty array with newline", "[]\n", true},
		{"empty with whitespace", "  []  ", true},
		{"empty array with inner space", "[ ]", true},
		{"non-empty JSON", `[{"Name":"backend"}]`, false},
		{"whitespace only", "   ", true},
		{"single container", `{"Name":"backend","State":"running"}`, false},
		{"NDJSON multiple containers", "{\"Name\":\"backend\"}\n{\"Name\":\"web\"}\n", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if got := isEmptyPS(tt.output); got != tt.want {
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
