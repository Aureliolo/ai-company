-- Modify "audit_entries" table
ALTER TABLE "audit_entries" DROP CONSTRAINT "audit_entries_pkey", ADD PRIMARY KEY ("id", "timestamp");
-- Modify "cost_records" table
ALTER TABLE "cost_records" DROP CONSTRAINT "cost_records_pkey", ADD PRIMARY KEY ("rowid", "timestamp");
-- Modify "enforce_ceo_minimum" function
CREATE OR REPLACE FUNCTION "enforce_ceo_minimum" () RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(42001);
    IF NOT EXISTS (SELECT 1 FROM users WHERE role = 'ceo') THEN
        RAISE EXCEPTION 'Cannot remove the last CEO'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
-- Modify "enforce_owner_minimum" function
CREATE OR REPLACE FUNCTION "enforce_owner_minimum" () RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(42002);
    IF NOT EXISTS (
        SELECT 1 FROM users WHERE org_roles @> '["owner"]'::jsonb
    ) THEN
        RAISE EXCEPTION 'Cannot remove the last owner'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
