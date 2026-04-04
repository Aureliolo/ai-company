import { useEffect } from 'react'
import { useWorkflowsStore } from '@/stores/workflows'

interface WorkflowSelectorProps {
  currentId: string | null
  onChange: (id: string) => void
}

export function WorkflowSelector({ currentId, onChange }: WorkflowSelectorProps) {
  const workflows = useWorkflowsStore((s) => s.workflows)
  const loading = useWorkflowsStore((s) => s.listLoading)
  const fetchWorkflows = useWorkflowsStore((s) => s.fetchWorkflows)

  useEffect(() => {
    fetchWorkflows()
  }, [fetchWorkflows])

  if (loading && workflows.length === 0) {
    return (
      <select
        disabled
        className="h-7 w-44 rounded-md border border-border bg-surface px-2 text-xs text-muted-foreground"
        aria-label="Loading workflows"
      >
        <option>Loading...</option>
      </select>
    )
  }

  return (
    <select
      value={currentId ?? ''}
      onChange={(e) => {
        if (e.target.value) onChange(e.target.value)
      }}
      className="h-7 w-44 truncate rounded-md border border-border bg-surface px-2 text-xs text-foreground"
      aria-label="Select workflow"
    >
      {!currentId && <option value="">Select workflow</option>}
      {workflows.map((w) => (
        <option key={w.id} value={w.id}>
          {w.name}
        </option>
      ))}
    </select>
  )
}
