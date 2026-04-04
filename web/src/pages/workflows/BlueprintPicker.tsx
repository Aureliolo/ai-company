import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { FileCode2 } from 'lucide-react'
import { listBlueprints } from '@/api/endpoints/workflows'
import { Skeleton } from '@/components/ui/skeleton'
import { StatPill } from '@/components/ui/stat-pill'
import { createLogger } from '@/lib/logger'
import { cardEntrance, staggerChildren } from '@/lib/motion'
import { getErrorMessage } from '@/utils/errors'
import { formatLabel } from '@/utils/format'
import { cn } from '@/lib/utils'
import type { BlueprintInfo } from '@/api/types'

const log = createLogger('blueprint-picker')

interface BlueprintPickerProps {
  selectedBlueprint: string | null
  onSelect: (name: string | null) => void
  workflowTypeFilter?: string | null
}

export function BlueprintPicker({
  selectedBlueprint,
  onSelect,
  workflowTypeFilter,
}: BlueprintPickerProps) {
  const [state, setState] = useState<{
    blueprints: readonly BlueprintInfo[]
    loading: boolean
    error: string | null
  }>({ blueprints: [], loading: true, error: null })

  useEffect(() => {
    let cancelled = false

    listBlueprints()
      .then((data) => {
        if (!cancelled) {
          setState({ blueprints: data, loading: false, error: null })
        }
      })
      .catch((err) => {
        if (!cancelled) {
          log.warn('Failed to fetch blueprints', err)
          setState({ blueprints: [], loading: false, error: getErrorMessage(err) })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  const { blueprints, loading, error } = state

  const filtered = workflowTypeFilter
    ? blueprints.filter((bp) => bp.workflow_type === workflowTypeFilter)
    : blueprints

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-grid-gap">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-28 rounded-lg" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-md border border-danger/30 bg-danger/5 p-card text-sm text-danger"
      >
        Failed to load blueprints: {error}
      </div>
    )
  }

  return (
    <motion.div
      className="grid grid-cols-2 gap-grid-gap"
      variants={staggerChildren}
      initial="hidden"
      animate="visible"
    >
      {filtered.map((bp) => (
        <motion.button
          key={bp.name}
          type="button"
          variants={cardEntrance}
          onClick={() =>
            onSelect(selectedBlueprint === bp.name ? null : bp.name)
          }
          className={cn(
            'flex flex-col items-start gap-2 rounded-lg border p-card text-left transition-colors',
            'hover:border-accent/50 hover:bg-card-hover',
            selectedBlueprint === bp.name
              ? 'border-accent bg-accent/5'
              : 'border-border bg-card',
          )}
        >
          <div className="flex w-full items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCode2 className="size-4 text-muted" />
              <span className="text-sm font-medium text-foreground">
                {bp.display_name}
              </span>
            </div>
            <span className="rounded-md bg-muted/20 px-1.5 py-0.5 text-xs text-muted">
              {formatLabel(bp.workflow_type)}
            </span>
          </div>

          <p className="line-clamp-2 text-xs text-muted">{bp.description}</p>

          <div className="flex gap-2">
            <StatPill label="Nodes" value={bp.node_count} />
            <StatPill label="Edges" value={bp.edge_count} />
          </div>
        </motion.button>
      ))}
    </motion.div>
  )
}
