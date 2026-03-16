package verify

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	sigverify "github.com/sigstore/sigstore-go/pkg/verify"
)

func TestVerifyProvenanceEmptyDigest(t *testing.T) {
	ref := ImageRef{
		Registry:   "ghcr.io",
		Repository: "test/image",
		Tag:        "1.0.0",
	}
	err := VerifyProvenance(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if err == nil {
		t.Fatal("expected error for empty digest")
	}
	if !strings.Contains(err.Error(), "digest not resolved") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestVerifyProvenanceNoReferrers(t *testing.T) {
	repo := "test/image"
	emptyIndex := `{"schemaVersion":2,"mediaType":"application/vnd.oci.image.index.v1+json","manifests":[]}`

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/v2/":
			w.WriteHeader(http.StatusOK)
		case strings.Contains(r.URL.Path, "/referrers/"):
			w.Header().Set("Content-Type", "application/vnd.oci.image.index.v1+json")
			_, _ = w.Write([]byte(emptyIndex))
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

	err := VerifyProvenance(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if err == nil {
		t.Fatal("expected error when no attestations found")
	}
	if !strings.Contains(err.Error(), "no SLSA provenance attestations") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestValidateSLSAPredicate(t *testing.T) {
	tests := []struct {
		name          string
		predicateType string
		payloadType   string
		wantErr       bool
		errContains   string
	}{
		{
			name:          "valid SLSA v1",
			predicateType: "https://slsa.dev/provenance/v1",
			payloadType:   DSSEPayloadType,
		},
		{
			name:          "wrong predicate type",
			predicateType: "https://example.com/wrong-type",
			payloadType:   DSSEPayloadType,
			wantErr:       true,
			errContains:   "unexpected predicate type",
		},
		{
			name:          "wrong payload type",
			predicateType: "https://slsa.dev/provenance/v1",
			payloadType:   "application/octet-stream",
			wantErr:       true,
			errContains:   "unexpected DSSE payload type",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			statement := inTotoStatement{PredicateType: tt.predicateType}
			statementJSON, err := json.Marshal(statement)
			if err != nil {
				t.Fatalf("failed to marshal statement: %v", err)
			}

			envelope := dsseEnvelope{
				PayloadType: tt.payloadType,
				Payload:     base64.StdEncoding.EncodeToString(statementJSON),
			}

			err = validateSLSAPredicate(envelope)
			if (err != nil) != tt.wantErr {
				t.Fatalf("validateSLSAPredicate() error = %v, wantErr %v", err, tt.wantErr)
			}
			if tt.errContains != "" && err != nil {
				if !strings.Contains(err.Error(), tt.errContains) {
					t.Errorf("error %q should contain %q", err.Error(), tt.errContains)
				}
			}
		})
	}
}

// TestVerifyProvenanceInvalidAttestation verifies that VerifyProvenance rejects
// an attestation with an invalid structure. The mock attestation has a non-SLSA
// predicate and no Sigstore bundle, so VerifyProvenance may fail at either
// validateSLSAPredicate or verifyAttestationBundle — the test exercises the
// general invalid-attestation error path, not a specific validation step.
func TestVerifyProvenanceInvalidAttestation(t *testing.T) {
	repo := "test/image"
	attestDigest := "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

	statement := inTotoStatement{
		PredicateType: "https://example.com/not-slsa",
	}
	statementJSON, err := json.Marshal(statement)
	if err != nil {
		t.Fatalf("failed to marshal statement: %v", err)
	}
	envelope := dsseEnvelope{
		PayloadType: DSSEPayloadType,
		Payload:     base64.StdEncoding.EncodeToString(statementJSON),
	}
	envelopeJSON, err := json.Marshal(envelope)
	if err != nil {
		t.Fatalf("failed to marshal envelope: %v", err)
	}

	attestManifest := ociManifest{
		SchemaVersion: 2,
		MediaType:     "application/vnd.oci.image.manifest.v1+json",
		Config: ociDescriptor{
			MediaType: "application/vnd.oci.image.config.v1+json",
			Digest:    "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
			Size:      2,
		},
		Layers: []ociLayerDescriptor{
			{
				MediaType: "application/vnd.in-toto+json",
				Digest:    "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
				Size:      len(envelopeJSON),
			},
		},
	}
	attestManifestJSON, err := json.Marshal(attestManifest)
	if err != nil {
		t.Fatalf("failed to marshal attestation manifest: %v", err)
	}

	referrerIndex := fmt.Sprintf(`{
		"schemaVersion": 2,
		"mediaType": "application/vnd.oci.image.index.v1+json",
		"manifests": [{
			"mediaType": "application/vnd.oci.image.manifest.v1+json",
			"digest": "%s",
			"size": %d,
			"artifactType": "application/vnd.in-toto+json"
		}]
	}`, attestDigest, len(attestManifestJSON))

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/v2/":
			w.WriteHeader(http.StatusOK)
		case strings.Contains(r.URL.Path, "/referrers/"):
			w.Header().Set("Content-Type", "application/vnd.oci.image.index.v1+json")
			_, _ = w.Write([]byte(referrerIndex))
		case r.URL.Path == fmt.Sprintf("/v2/%s/manifests/%s", repo, attestDigest):
			w.Header().Set("Content-Type", "application/vnd.oci.image.manifest.v1+json")
			w.Header().Set("Docker-Content-Digest", attestDigest)
			_, _ = w.Write(attestManifestJSON)
		case strings.Contains(r.URL.Path, "/blobs/sha256:bbbb"):
			_, _ = w.Write([]byte("{}"))
		case strings.Contains(r.URL.Path, "/blobs/sha256:cccc"):
			_, _ = w.Write(envelopeJSON)
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

	err = VerifyProvenance(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if err == nil {
		t.Fatal("expected error for invalid attestation")
	}
	if !strings.Contains(err.Error(), "no valid SLSA provenance attestation") {
		t.Errorf("expected provenance attestation error, got: %v", err)
	}
}
