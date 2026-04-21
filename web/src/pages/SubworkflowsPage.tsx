import { useCallback, useState } from 'react'
import { Search } from 'lucide-react'
import { useSubworkflowsData } from '@/hooks/useSubworkflowsData'
import { useSubworkflowsStore } from '@/stores/subworkflows'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorBanner } from '@/components/ui/error-banner'
import { InputField } from '@/components/ui/input-field'
import { Skeleton } from '@/components/ui/skeleton'
import type { SubworkflowSummary } from '@/api/types/workflows'
import { SubworkflowCard } from './subworkflows/SubworkflowCard'
import { SubworkflowDetailDrawer } from './subworkflows/SubworkflowDetailDrawer'

export default function SubworkflowsPage() {
  const [selected, setSelected] = useState<SubworkflowSummary | null>(null)
  const { filteredSubworkflows, loading, error } = useSubworkflowsData()
  const searchQuery = useSubworkflowsStore((s) => s.searchQuery)
  const setSearchQuery = useSubworkflowsStore((s) => s.setSearchQuery)

  const handleSearch = useCallback(
    (value: string) => {
      setSearchQuery(value)
    },
    [setSearchQuery],
  )

  const handleCardClick = useCallback((sub: SubworkflowSummary) => {
    setSelected(sub)
  }, [])

  if (loading && filteredSubworkflows.length === 0) {
    return (
      <div className="space-y-section-gap">
        <Skeleton className="h-8 w-48 rounded" />
        <div className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Subworkflows</h1>
        <span className="text-sm text-muted-foreground">
          {filteredSubworkflows.length} subworkflow{filteredSubworkflows.length !== 1 ? 's' : ''}
        </span>
      </div>

      {error && (
        <ErrorBanner severity="error" title="Could not load subworkflows" description={error} />
      )}

      <div className="max-w-sm">
        <InputField
          label="Search subworkflows"
          value={searchQuery}
          onValueChange={handleSearch}
          placeholder="Search by name, description, or ID..."
          type="text"
        >
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
        </InputField>
      </div>

      {filteredSubworkflows.length === 0 ? (
        <EmptyState
          title="No subworkflows"
          description={
            searchQuery
              ? 'No subworkflows match your search.'
              : 'Publish a workflow as a subworkflow to see it here.'
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
          {filteredSubworkflows.map((sub) => (
            <SubworkflowCard
              key={sub.subworkflow_id}
              subworkflow={sub}
              onClick={handleCardClick}
            />
          ))}
        </div>
      )}

      <SubworkflowDetailDrawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        subworkflow={selected}
      />
    </div>
  )
}
