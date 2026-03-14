package selfupdate

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"runtime"
	"testing"
)

func TestAssetName(t *testing.T) {
	name := assetName()
	if name == "" {
		t.Fatal("assetName returned empty")
	}
	// Should contain OS and arch.
	want := fmt.Sprintf("synthorg_%s_%s", runtime.GOOS, runtime.GOARCH)
	if len(name) < len(want) {
		t.Errorf("assetName = %q, want prefix %q", name, want)
	}
}

func TestVerifyChecksum(t *testing.T) {
	data := []byte("hello world")
	hash := sha256.Sum256(data)
	checksum := hex.EncodeToString(hash[:])

	checksums := fmt.Sprintf("deadbeef  wrong_file.tar.gz\n%s  test_asset.tar.gz\n", checksum)

	// Valid checksum.
	if err := verifyChecksum(data, []byte(checksums), "test_asset.tar.gz"); err != nil {
		t.Errorf("expected valid checksum: %v", err)
	}

	// Invalid checksum.
	if err := verifyChecksum([]byte("wrong data"), []byte(checksums), "test_asset.tar.gz"); err == nil {
		t.Error("expected checksum mismatch error")
	}

	// Missing asset.
	if err := verifyChecksum(data, []byte(checksums), "missing.tar.gz"); err == nil {
		t.Error("expected missing asset error")
	}
}
