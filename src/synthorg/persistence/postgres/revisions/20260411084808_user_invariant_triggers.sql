-- Create "enforce_ceo_minimum" function
CREATE FUNCTION "enforce_ceo_minimum" () RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE role = 'ceo') THEN
        RAISE EXCEPTION 'Cannot remove the last CEO'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
-- Create trigger "trg_enforce_ceo_minimum"
CREATE CONSTRAINT TRIGGER "trg_enforce_ceo_minimum" AFTER UPDATE OF "role" ON "users" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN ((old.role = 'ceo'::text) AND (new.role <> 'ceo'::text)) EXECUTE FUNCTION "enforce_ceo_minimum"();
-- Create "enforce_owner_minimum" function
CREATE FUNCTION "enforce_owner_minimum" () RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM users WHERE org_roles @> '["owner"]'::jsonb
    ) THEN
        RAISE EXCEPTION 'Cannot remove the last owner'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
-- Create trigger "trg_enforce_owner_minimum"
CREATE CONSTRAINT TRIGGER "trg_enforce_owner_minimum" AFTER UPDATE OF "org_roles" ON "users" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN ((old.org_roles @> '["owner"]'::jsonb) AND (NOT (new.org_roles @> '["owner"]'::jsonb))) EXECUTE FUNCTION "enforce_owner_minimum"();
