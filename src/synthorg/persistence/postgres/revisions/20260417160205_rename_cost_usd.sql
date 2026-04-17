-- Modify "agent_states" table
ALTER TABLE "agent_states" DROP CONSTRAINT "agent_states_accumulated_cost_usd_check", DROP CONSTRAINT "agent_states_check", ADD CONSTRAINT "agent_states_check" CHECK (((status = 'idle'::text) AND (execution_id IS NULL) AND (task_id IS NULL) AND (started_at IS NULL) AND (turn_count = 0) AND (accumulated_cost = (0.0)::double precision)) OR ((status = ANY (ARRAY['executing'::text, 'paused'::text])) AND (execution_id IS NOT NULL) AND (started_at IS NOT NULL))), ADD CONSTRAINT "agent_states_accumulated_cost_check" CHECK (accumulated_cost >= (0.0)::double precision), DROP COLUMN "accumulated_cost_usd", ADD COLUMN "accumulated_cost" double precision NOT NULL DEFAULT 0.0;
-- Modify "cost_records" table
ALTER TABLE "cost_records" DROP COLUMN "cost_usd", ADD COLUMN "cost" double precision NOT NULL;
-- Modify "task_metrics" table
ALTER TABLE "task_metrics" DROP COLUMN "cost_usd", ADD COLUMN "cost" double precision NOT NULL;
