import { useState } from 'react'
import { Settings2, Shield } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { SkeletonText } from '@/components/ui/skeleton'
import { useRulesData } from '@/hooks/useRulesData'

import { RulesDrawer } from './RulesDrawer'

export function MetaRuleStatus() {
  const { allRules, metrics, loading, error, refresh } = useRulesData()
  const [drawerOpen, setDrawerOpen] = useState(false)

  if (loading && allRules.length === 0) {
    return (
      <div className="space-y-2 p-2">
        <SkeletonText lines={3} />
      </div>
    )
  }

  if (error && allRules.length === 0) {
    return (
      <EmptyState
        icon={Shield}
        title="Failed to Load Rules"
        description={error}
      />
    )
  }

  const enabledCount = allRules.filter((r) => r.enabled).length
  const customCount = allRules.filter((r) => r.type === 'custom').length

  return (
    <>
      <div className="space-y-section-gap">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-foreground">
              <span className="font-medium">{enabledCount}</span>
              <span className="text-muted-foreground">
                {' '}of {allRules.length} rules enabled
              </span>
            </p>
            {customCount > 0 && (
              <p className="text-micro text-muted-foreground">
                {customCount} custom rule{customCount !== 1 ? 's' : ''}
              </p>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDrawerOpen(true)}
          >
            <Settings2 className="mr-1 size-3.5" />
            Manage Rules
          </Button>
        </div>
      </div>

      <RulesDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        allRules={allRules}
        metrics={metrics}
        onRefresh={refresh}
      />
    </>
  )
}
