package verify

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const testDigest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

// newMockRegistry creates a minimal OCI distribution spec registry that
// responds to HEAD /v2/<repo>/manifests/<tag> with the given digest.
func newMockRegistry(t *testing.T, repo, tag, digest string) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := fmt.Sprintf("/v2/%s/manifests/%s", repo, tag)
		if r.Method == http.MethodGet && r.URL.Path == "/v2/" {
			// OCI distribution spec version check.
			w.WriteHeader(http.StatusOK)
			return
		}
		if r.URL.Path == expectedPath && (r.Method == http.MethodHead || r.Method == http.MethodGet) {
			w.Header().Set("Docker-Content-Digest", digest)
			w.Header().Set("Content-Type", "application/vnd.oci.image.manifest.v1+json")
			w.Header().Set("Content-Length", "0")
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
}

func TestResolveDigestSuccess(t *testing.T) {
	repo := "test/image"
	tag := "1.0.0"
	srv := newMockRegistry(t, repo, tag, testDigest)
	defer srv.Close()

	// Extract host from server URL (strip http://).
	host := strings.TrimPrefix(srv.URL, "http://")

	ref := ImageRef{
		Registry:   host,
		Repository: repo,
		Tag:        tag,
	}

	digest, err := ResolveDigest(context.Background(), ref)
	if err != nil {
		t.Fatalf("ResolveDigest() error: %v", err)
	}
	if digest != testDigest {
		t.Errorf("digest = %q, want %q", digest, testDigest)
	}
}

func TestResolveDigestNotFound(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v2/" {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: "test/missing",
		Tag:        "1.0.0",
	}

	_, err := ResolveDigest(context.Background(), ref)
	if err == nil {
		t.Fatal("expected error for missing image")
	}
}

func TestResolveDigestServerError(t *testing.T) {
	// Registry that returns 500 for both HEAD and GET — verifies that
	// errors propagate when the GET fallback also fails.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v2/" {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: "test/image",
		Tag:        "1.0.0",
	}

	_, err := ResolveDigest(context.Background(), ref)
	if err == nil {
		t.Fatal("expected error for server error")
	}
}

func TestResolveDigestHEADFallbackToGET(t *testing.T) {
	// Registry that returns 405 for HEAD but serves manifests via GET.
	repo := "test/image"
	tag := "1.0.0"
	manifestBody := `{"schemaVersion":2}`
	// go-containerregistry computes sha256 from the GET response body.
	expectedDigest := "sha256:bafebd36189ad3688b7b3915ea55d461e0bfcfbdde11e54b0a123999fb6be50f"

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		expectedPath := fmt.Sprintf("/v2/%s/manifests/%s", repo, tag)
		if r.Method == http.MethodGet && r.URL.Path == "/v2/" {
			w.WriteHeader(http.StatusOK)
			return
		}
		if r.URL.Path == expectedPath {
			if r.Method == http.MethodHead {
				w.WriteHeader(http.StatusMethodNotAllowed)
				return
			}
			if r.Method == http.MethodGet {
				w.Header().Set("Content-Type", "application/vnd.oci.image.manifest.v1+json")
				_, _ = w.Write([]byte(manifestBody))
				return
			}
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: repo,
		Tag:        tag,
	}

	digest, err := ResolveDigest(context.Background(), ref)
	if err != nil {
		t.Fatalf("ResolveDigest() error: %v", err)
	}
	if digest != expectedDigest {
		t.Errorf("digest = %q, want %q", digest, expectedDigest)
	}
}

func TestResolveDigestContextCancelled(t *testing.T) {
	srv := newMockRegistry(t, "test/image", "1.0.0", testDigest)
	defer srv.Close()

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // cancel immediately

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: "test/image",
		Tag:        "1.0.0",
	}

	_, err := ResolveDigest(ctx, ref)
	if err == nil {
		t.Fatal("expected error for cancelled context")
	}
}
