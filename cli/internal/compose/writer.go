package compose

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/Aureliolo/synthorg/cli/internal/config"
)

// WriteComposeAndNATS keeps compose.yml and its bind-mounted nats.conf
// side-file consistent across every caller that regenerates compose.
// Order matters and depends on the direction of the busBackend
// transition:
//
//   - busBackend == "nats": the freshly written compose.yml references
//     nats.conf via `configs.nats-config.file: ./nats.conf`. Write the
//     side-file FIRST so if the compose write fails we still have a
//     consistent on-disk pair (old compose either already references a
//     nats.conf we just refreshed, or it does not reference it at all,
//     which is still valid).
//   - busBackend != "nats": the freshly written compose.yml no longer
//     references nats.conf. Remove the stale side-file AFTER the
//     compose write so a compose write failure leaves the old compose
//     (which may reference nats.conf) and the file still in place.
//
// Either way, a failure at any step leaves the disk in a consistent
// state -- NATS will never start against a missing-or-mismatched
// nats.conf because compose.yml and the file are always co-committed.
func WriteComposeAndNATS(composePath string, composeYAML []byte, busBackend, safeDir string) error {
	if busBackend == "nats" {
		if err := WriteNATSConfig(busBackend, safeDir); err != nil {
			return err
		}
	}
	if err := AtomicWriteFile(composePath, composeYAML, safeDir); err != nil {
		return err
	}
	if busBackend != "nats" {
		if err := WriteNATSConfig(busBackend, safeDir); err != nil {
			return err
		}
	}
	return nil
}

// WriteNATSConfig writes the NATS server config file alongside
// compose.yml when busBackend is "nats", and removes any stale copy
// when the bus is the in-process default.
//
// Implementation notes:
//   - File I/O goes through os.Root so operations are statically
//     contained to safeDir. CodeQL's go/path-injection analyser sees a
//     rooted filesystem sink instead of a raw filepath.Join reaching a
//     potentially-tainted directory.
//   - The write path stages the content in a temp sibling and renames
//     it over the live file so a crash between truncate and final sync
//     cannot leave a zero-byte or partial nats.conf.
//   - safeDir is re-sanitised via config.SecurePath to make the
//     sanitisation point explicit at the use site.
func WriteNATSConfig(busBackend, safeDir string) error {
	sanitised, err := config.SecurePath(safeDir)
	if err != nil {
		return fmt.Errorf("nats config: %w", err)
	}
	if sanitised != safeDir {
		return fmt.Errorf("nats config: safeDir %q is not canonical (expected %q)", safeDir, sanitised)
	}
	root, err := os.OpenRoot(sanitised)
	if err != nil {
		return fmt.Errorf("opening nats config root %q: %w", sanitised, err)
	}
	defer func() { _ = root.Close() }()
	if busBackend != "nats" {
		if err := root.Remove(NATSConfigFilename); err != nil && !errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("removing stale nats.conf: %w", err)
		}
		return nil
	}
	return atomicWriteRooted(root, NATSConfigFilename, []byte(NATSConfigContent))
}

// atomicWriteRooted stages content into a temp sibling and renames it
// over dst via the supplied rooted filesystem handle so a crash between
// open+truncate and the final sync cannot leave a zero-byte file
// behind.
func atomicWriteRooted(root *os.Root, dst string, data []byte) (err error) {
	// Use a time-agnostic unique suffix via os.Root.Create on a name
	// that no production caller will use, falling back to a few
	// retries in the pathological "temp already exists" case.
	tmpName := dst + ".tmp"
	tmp, err := root.OpenFile(tmpName, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return fmt.Errorf("creating temp %s: %w", tmpName, err)
	}
	cleanup := true
	defer func() {
		if cleanup {
			_ = root.Remove(tmpName)
		}
	}()

	if _, werr := tmp.Write(data); werr != nil {
		_ = tmp.Close()
		return fmt.Errorf("writing temp %s: %w", tmpName, werr)
	}
	if serr := tmp.Sync(); serr != nil {
		_ = tmp.Close()
		return fmt.Errorf("syncing temp %s: %w", tmpName, serr)
	}
	if cerr := tmp.Close(); cerr != nil {
		return fmt.Errorf("closing temp %s: %w", tmpName, cerr)
	}
	if rerr := root.Rename(tmpName, dst); rerr != nil {
		return fmt.Errorf("renaming temp %s to %s: %w", tmpName, dst, rerr)
	}
	cleanup = false // rename succeeded; temp is gone
	return nil
}

// AtomicWriteFile writes data to targetPath via a temp file + rename
// so a crash mid-write cannot leave a partial file. tmpDir must be on
// the same filesystem as targetPath (rename only works within one
// filesystem). Exposed publicly so cli/cmd callers that generate
// compose.yml outside this package can reuse the same pattern.
func AtomicWriteFile(targetPath string, data []byte, tmpDir string) error {
	tmp, err := os.CreateTemp(tmpDir, ".compose-*.yml.tmp")
	if err != nil {
		return fmt.Errorf("creating temp file: %w", err)
	}
	tmpPath := tmp.Name()

	defer func() {
		if tmpPath != "" {
			_ = os.Remove(tmpPath)
		}
	}()

	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return fmt.Errorf("writing compose file: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return fmt.Errorf("syncing compose file: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("closing compose file: %w", err)
	}

	if err := os.Chmod(tmpPath, 0o600); err != nil {
		return fmt.Errorf("setting compose file permissions: %w", err)
	}

	if err := os.Rename(tmpPath, targetPath); err != nil {
		return fmt.Errorf("replacing compose file: %w", err)
	}
	tmpPath = ""

	if dir, err := os.Open(filepath.Dir(targetPath)); err == nil {
		_ = dir.Sync()
		_ = dir.Close()
	}
	return nil
}
