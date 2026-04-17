-- Rename "agent_states.accumulated_cost_usd" to "accumulated_cost" (lossless)
ALTER TABLE "agent_states" RENAME COLUMN "accumulated_cost_usd" TO "accumulated_cost";
-- Update CHECK constraints to reference the renamed column
ALTER TABLE "agent_states" DROP CONSTRAINT "agent_states_accumulated_cost_usd_check", DROP CONSTRAINT "agent_states_check", ADD CONSTRAINT "agent_states_accumulated_cost_check" CHECK (accumulated_cost >= (0.0)::double precision), ADD CONSTRAINT "agent_states_check" CHECK (((status = 'idle'::text) AND (execution_id IS NULL) AND (task_id IS NULL) AND (started_at IS NULL) AND (turn_count = 0) AND (accumulated_cost = (0.0)::double precision)) OR ((status = ANY (ARRAY['executing'::text, 'paused'::text])) AND (execution_id IS NOT NULL) AND (started_at IS NOT NULL)));
-- Rename "cost_records.cost_usd" to "cost" (lossless)
ALTER TABLE "cost_records" RENAME COLUMN "cost_usd" TO "cost";
-- Rename "task_metrics.cost_usd" to "cost" (lossless)
ALTER TABLE "task_metrics" RENAME COLUMN "cost_usd" TO "cost";
