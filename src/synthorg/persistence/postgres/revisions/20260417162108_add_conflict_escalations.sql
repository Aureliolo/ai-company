-- Create "conflict_escalations" table
CREATE TABLE "conflict_escalations" (
  "id" text NOT NULL,
  "conflict_id" text NOT NULL,
  "conflict_json" jsonb NOT NULL,
  "status" text NOT NULL DEFAULT 'pending',
  "created_at" timestamptz NOT NULL,
  "expires_at" timestamptz NULL,
  "decided_at" timestamptz NULL,
  "decided_by" text NULL,
  "decision_json" jsonb NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "conflict_escalations_check" CHECK ((status <> 'decided'::text) OR ((decision_json IS NOT NULL) AND (decided_at IS NOT NULL) AND (decided_by IS NOT NULL))),
  CONSTRAINT "conflict_escalations_check1" CHECK ((status <> 'pending'::text) OR ((decision_json IS NULL) AND (decided_at IS NULL))),
  CONSTRAINT "conflict_escalations_conflict_id_check" CHECK (length(TRIM(BOTH FROM conflict_id)) > 0),
  CONSTRAINT "conflict_escalations_id_check" CHECK (length(TRIM(BOTH FROM id)) > 0),
  CONSTRAINT "conflict_escalations_status_check" CHECK (status = ANY (ARRAY['pending'::text, 'decided'::text, 'expired'::text, 'cancelled'::text]))
);
-- Create index "idx_conflict_escalations_conflict_id" to table: "conflict_escalations"
CREATE INDEX "idx_conflict_escalations_conflict_id" ON "conflict_escalations" ("conflict_id");
-- Create index "idx_conflict_escalations_status_created" to table: "conflict_escalations"
CREATE INDEX "idx_conflict_escalations_status_created" ON "conflict_escalations" ("status", "created_at");
