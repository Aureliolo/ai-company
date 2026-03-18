package verify

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	v1 "github.com/google/go-containerregistry/pkg/v1"
	sigverify "github.com/sigstore/sigstore-go/pkg/verify"
)

func TestParseDigest(t *testing.T) {
	tests := []struct {
		name    string
		digest  string
		wantErr bool
	}{
		{"valid", "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890", false},
		{"no colon", "sha256abcdef", true},
		{"unsupported algo", "sha512:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890", true},
		{"invalid hex", "sha256:xyz", true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			algo, b, err := parseDigest(tt.digest)
			if (err != nil) != tt.wantErr {
				t.Errorf("parseDigest(%q) error = %v, wantErr %v", tt.digest, err, tt.wantErr)
				return
			}
			if !tt.wantErr {
				if algo != "sha256" {
					t.Errorf("algo = %q, want sha256", algo)
				}
				expected, _ := hex.DecodeString(strings.SplitN(tt.digest, ":", 2)[1])
				if len(b) != len(expected) {
					t.Errorf("byte length = %d, want %d", len(b), len(expected))
				}
			}
		})
	}
}

func TestVerifyCosignSignatureEmptyDigest(t *testing.T) {
	ref := ImageRef{
		Registry:   "ghcr.io",
		Repository: "test/image",
		Tag:        "1.0.0",
	}
	err := VerifyCosignSignature(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if err == nil {
		t.Fatal("expected error for empty digest")
	}
	if !strings.Contains(err.Error(), "digest not resolved") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestVerifyCosignSignatureNoReferrers(t *testing.T) {
	// Precompute empty referrer index JSON outside the handler.
	emptyIdx := v1.IndexManifest{
		SchemaVersion: 2,
		MediaType:     "application/vnd.oci.image.index.v1+json",
		Manifests:     []v1.Descriptor{},
	}
	emptyIdxJSON, err := json.Marshal(emptyIdx)
	if err != nil {
		t.Fatalf("marshaling empty referrer index: %v", err)
	}

	// Mock registry that returns an empty referrer index.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/v2/":
			w.WriteHeader(http.StatusOK)
		case strings.Contains(r.URL.Path, "/referrers/"):
			w.Header().Set("Content-Type", "application/vnd.oci.image.index.v1+json")
			_, _ = w.Write(emptyIdxJSON)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer srv.Close()

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: "test/image",
		Tag:        "1.0.0",
		Digest:     testDigest,
	}

	verifyErr := VerifyCosignSignature(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if verifyErr == nil {
		t.Fatal("expected error when no cosign referrers exist")
	}
	if !errors.Is(verifyErr, ErrNoCosignSignatures) {
		t.Errorf("expected error to wrap ErrNoCosignSignatures, got: %v", verifyErr)
	}
}

// ociManifest is a minimal OCI image manifest for test fixtures.
type ociManifest struct {
	SchemaVersion int                  `json:"schemaVersion"`
	MediaType     string               `json:"mediaType"`
	Config        ociDescriptor        `json:"config"`
	Layers        []ociLayerDescriptor `json:"layers"`
	Annotations   map[string]string    `json:"annotations,omitempty"`
}

type ociDescriptor struct {
	MediaType string `json:"mediaType"`
	Digest    string `json:"digest"`
	Size      int    `json:"size"`
}

type ociLayerDescriptor struct {
	MediaType   string            `json:"mediaType"`
	Digest      string            `json:"digest"`
	Size        int               `json:"size"`
	Annotations map[string]string `json:"annotations,omitempty"`
}

func TestVerifyCosignSignatureInvalidBundle(t *testing.T) {
	// Mock registry that returns a cosign signature as an OCI referrer with invalid bundle.
	repo := "test/image"
	sigDigest := "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

	configJSON := `{}`
	layerContent := "dummy-layer-content"

	sigManifest := ociManifest{
		SchemaVersion: 2,
		MediaType:     "application/vnd.oci.image.manifest.v1+json",
		Config: ociDescriptor{
			MediaType: "application/vnd.oci.image.config.v1+json",
			Digest:    "sha256:44136fa355b311bfa616a15e4e5e6d84e4f455ce82fb1ed83b0a7f9e2c3d4a5b",
			Size:      len(configJSON),
		},
		Layers: []ociLayerDescriptor{
			{
				MediaType: cosignArtifactType,
				Digest:    "sha256:0000000000000000000000000000000000000000000000000000000000000001",
				Size:      len(layerContent),
				Annotations: map[string]string{
					cosignBundleAnnotation: `{"invalid": "bundle"}`,
				},
			},
		},
	}

	sigManifestJSON, err := json.Marshal(sigManifest)
	if err != nil {
		t.Fatalf("marshaling signature manifest: %v", err)
	}

	// Referrer index pointing to the signature manifest.
	referrerIdx := v1.IndexManifest{
		SchemaVersion: 2,
		MediaType:     "application/vnd.oci.image.index.v1+json",
		Manifests: []v1.Descriptor{
			{
				MediaType:    "application/vnd.oci.image.manifest.v1+json",
				Digest:       v1.Hash{Algorithm: "sha256", Hex: strings.TrimPrefix(sigDigest, "sha256:")},
				Size:         int64(len(sigManifestJSON)),
				ArtifactType: cosignArtifactType,
			},
		},
	}
	referrerIdxJSON, err := json.Marshal(referrerIdx)
	if err != nil {
		t.Fatalf("marshaling referrer index: %v", err)
	}

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/v2/":
			w.WriteHeader(http.StatusOK)
		case strings.Contains(r.URL.Path, "/referrers/"):
			w.Header().Set("Content-Type", "application/vnd.oci.image.index.v1+json")
			_, _ = w.Write(referrerIdxJSON)
		case r.URL.Path == fmt.Sprintf("/v2/%s/manifests/%s", repo, sigDigest):
			w.Header().Set("Content-Type", "application/vnd.oci.image.manifest.v1+json")
			w.Header().Set("Docker-Content-Digest", sigDigest)
			_, _ = w.Write(sigManifestJSON)
		case strings.Contains(r.URL.Path, "/blobs/"):
			if strings.Contains(r.URL.Path, "44136fa") {
				_, _ = w.Write([]byte(configJSON))
			} else {
				_, _ = w.Write([]byte(layerContent))
			}
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer srv.Close()

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: repo,
		Tag:        "1.0.0",
		Digest:     testDigest,
	}

	err = VerifyCosignSignature(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if err == nil {
		t.Fatal("expected error for invalid bundle JSON")
	}
	if !strings.Contains(err.Error(), "cosign signature") {
		t.Errorf("expected cosign signature verification error, got: %v", err)
	}
}

func TestErrNoCosignSignaturesIs(t *testing.T) {
	wrapped := fmt.Errorf("%w for ghcr.io/test:1.0", ErrNoCosignSignatures)
	if !errors.Is(wrapped, ErrNoCosignSignatures) {
		t.Errorf("errors.Is(%v, ErrNoCosignSignatures) = false, want true", wrapped)
	}
}
