package selfupdate

import (
	"encoding/json"
	"strings"
	"testing"

	protobundle "github.com/sigstore/protobuf-specs/gen/pb-go/bundle/v1"
	protocommon "github.com/sigstore/protobuf-specs/gen/pb-go/common/v1"
	protodsse "github.com/sigstore/protobuf-specs/gen/pb-go/dsse"
	"github.com/sigstore/sigstore-go/pkg/bundle"
)

func TestAssertSLSAProvenanceValidPredicate(t *testing.T) {
	statement := slsaStatement{
		PredicateType: "https://slsa.dev/provenance/v1",
	}
	payload, err := json.Marshal(statement)
	if err != nil {
		t.Fatalf("failed to marshal statement: %v", err)
	}

	b := &bundle.Bundle{Bundle: &protobundle.Bundle{
		Content: &protobundle.Bundle_DsseEnvelope{
			DsseEnvelope: &protodsse.Envelope{
				PayloadType: "application/vnd.in-toto+json",
				Payload:     payload,
			},
		},
	}}

	if err := assertSLSAProvenance(b); err != nil {
		t.Fatalf("assertSLSAProvenance() error: %v", err)
	}
}

func TestAssertSLSAProvenanceWrongPredicateType(t *testing.T) {
	statement := slsaStatement{
		PredicateType: "https://example.com/not-slsa",
	}
	payload, err := json.Marshal(statement)
	if err != nil {
		t.Fatalf("failed to marshal statement: %v", err)
	}

	b := &bundle.Bundle{Bundle: &protobundle.Bundle{
		Content: &protobundle.Bundle_DsseEnvelope{
			DsseEnvelope: &protodsse.Envelope{
				PayloadType: "application/vnd.in-toto+json",
				Payload:     payload,
			},
		},
	}}

	err = assertSLSAProvenance(b)
	if err == nil {
		t.Fatal("expected error for wrong predicate type")
	}
	if !strings.Contains(err.Error(), "unexpected predicate type") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestAssertSLSAProvenanceWrongPayloadType(t *testing.T) {
	b := &bundle.Bundle{Bundle: &protobundle.Bundle{
		Content: &protobundle.Bundle_DsseEnvelope{
			DsseEnvelope: &protodsse.Envelope{
				PayloadType: "application/octet-stream",
				Payload:     []byte("{}"),
			},
		},
	}}

	err := assertSLSAProvenance(b)
	if err == nil {
		t.Fatal("expected error for wrong payload type")
	}
	if !strings.Contains(err.Error(), "unexpected DSSE payload type") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestAssertSLSAProvenanceNoDSSE(t *testing.T) {
	// Bundle with message signature (not DSSE) — should pass silently.
	b := &bundle.Bundle{Bundle: &protobundle.Bundle{
		Content: &protobundle.Bundle_MessageSignature{
			MessageSignature: &protocommon.MessageSignature{
				MessageDigest: &protocommon.HashOutput{
					Algorithm: protocommon.HashAlgorithm_SHA2_256,
					Digest:    []byte("test"),
				},
				Signature: []byte("test-sig"),
			},
		},
	}}

	if err := assertSLSAProvenance(b); err != nil {
		t.Fatalf("non-DSSE bundle should not error: %v", err)
	}
}

func TestAssertSLSAProvenanceInvalidJSON(t *testing.T) {
	b := &bundle.Bundle{Bundle: &protobundle.Bundle{
		Content: &protobundle.Bundle_DsseEnvelope{
			DsseEnvelope: &protodsse.Envelope{
				PayloadType: "application/vnd.in-toto+json",
				Payload:     []byte("not-valid-json"),
			},
		},
	}}

	err := assertSLSAProvenance(b)
	if err == nil {
		t.Fatal("expected error for invalid JSON payload")
	}
}
