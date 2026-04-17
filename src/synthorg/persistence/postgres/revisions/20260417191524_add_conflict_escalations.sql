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
  CONSTRAINT "conflict_escalations_check1" CHECK ((status <> 'pending'::text) OR ((decision_json IS NULL) AND (decided_at IS NULL) AND (decided_by IS NULL))),
  CONSTRAINT "conflict_escalations_check2" CHECK ((status <> ALL (ARRAY['expired'::text, 'cancelled'::text])) OR (decision_json IS NULL)),
  CONSTRAINT "conflict_escalations_conflict_id_check" CHECK (length(TRIM(BOTH FROM conflict_id)) > 0),
  CONSTRAINT "conflict_escalations_id_check" CHECK (length(TRIM(BOTH FROM id)) > 0),
  CONSTRAINT "conflict_escalations_status_check" CHECK (status = ANY (ARRAY['pending'::text, 'decided'::text, 'expired'::text, 'cancelled'::text]))
);
-- Create index "idx_conflict_escalations_conflict_id" to table: "conflict_escalations"
CREATE INDEX "idx_conflict_escalations_conflict_id" ON "conflict_escalations" ("conflict_id");
-- Create index "idx_conflict_escalations_status_created" to table: "conflict_escalations"
CREATE INDEX "idx_conflict_escalations_status_created" ON "conflict_escalations" ("status", "created_at");
-- Create index "idx_conflict_escalations_status_expires_at" to table: "conflict_escalations"
CREATE INDEX "idx_conflict_escalations_status_expires_at" ON "conflict_escalations" ("status", "expires_at");
-- Create index "idx_conflict_escalations_unique_pending_conflict" to table: "conflict_escalations"
CREATE UNIQUE INDEX "idx_conflict_escalations_unique_pending_conflict" ON "conflict_escalations" ("conflict_id") WHERE (status = 'pending'::text);
-- Create "notify_conflict_escalation_event" function
CREATE FUNCTION "notify_conflict_escalation_event" () RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (TG_OP = 'UPDATE' AND OLD.status = 'pending' AND NEW.status <> 'pending') THEN
        PERFORM pg_notify(
            'conflict_escalation_events',
            NEW.id || ':' || NEW.status
        );
    END IF;
    RETURN NEW;
END;
$$;
-- Create trigger "conflict_escalations_notify_after_update"
CREATE TRIGGER "conflict_escalations_notify_after_update" AFTER UPDATE ON "conflict_escalations" FOR EACH ROW EXECUTE FUNCTION "notify_conflict_escalation_event"();
