-- Create trigger "enforce_ceo_minimum"
CREATE TRIGGER `enforce_ceo_minimum` BEFORE UPDATE OF `role` ON `users` FOR EACH ROW WHEN OLD.role = 'ceo' AND NEW.role != 'ceo' BEGIN
    SELECT RAISE(ABORT, 'Cannot remove the last CEO')
    WHERE (SELECT COUNT(*) FROM users WHERE role = 'ceo' AND id != OLD.id) = 0;
END;
-- Create trigger "enforce_owner_minimum"
CREATE TRIGGER `enforce_owner_minimum` BEFORE UPDATE OF `org_roles` ON `users` FOR EACH ROW WHEN EXISTS (SELECT 1 FROM json_each(OLD.org_roles) WHERE value = 'owner')
  AND NOT EXISTS (SELECT 1 FROM json_each(NEW.org_roles) WHERE value = 'owner') BEGIN
    SELECT RAISE(ABORT, 'Cannot remove the last owner')
    WHERE (
        SELECT COUNT(*) FROM users u, json_each(u.org_roles) je
        WHERE u.id != OLD.id AND je.value = 'owner'
    ) = 0;
END;
