import { useEffect, useState } from 'react'
import { listWorkflows } from '@/api/endpoints/workflows'
import type { WorkflowDefinition } from '@/api/types'

interface WorkflowSelectorProps {
  currentId: string | null
  onChange: (id: string) => void
}

export function WorkflowSelector({ currentId, onChange }: WorkflowSelectorProps) {
  const [workflows, setWorkflows] = useState<readonly WorkflowDefinition[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    listWorkflows({ limit: 100 })
      .then((result) => {
        if (!cancelled) setWorkflows(result.data)
      })
      .catch(() => {
        // Silently ignore -- selector is non-critical
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

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
