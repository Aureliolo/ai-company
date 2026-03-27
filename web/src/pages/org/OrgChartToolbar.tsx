import { GitBranch, Network, Maximize, ZoomIn, ZoomOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type ViewMode = 'hierarchy' | 'force'

interface OrgChartToolbarProps {
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  onFitView: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  className?: string
}

export function OrgChartToolbar({
  viewMode,
  onViewModeChange,
  onFitView,
  onZoomIn,
  onZoomOut,
  className,
}: OrgChartToolbarProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-1 rounded-lg border border-border bg-card p-1',
        className,
      )}
      data-testid="org-chart-toolbar"
    >
      <div className="flex items-center rounded-md border border-border">
        <Button
          variant={viewMode === 'hierarchy' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => onViewModeChange('hierarchy')}
          aria-label="Hierarchy view"
          aria-pressed={viewMode === 'hierarchy'}
          className="h-7 gap-1.5 rounded-r-none px-2 text-xs"
        >
          <GitBranch className="size-3.5" aria-hidden="true" />
          Hierarchy
        </Button>
        <Button
          variant={viewMode === 'force' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => onViewModeChange('force')}
          aria-label="Communication view"
          aria-pressed={viewMode === 'force'}
          className="h-7 gap-1.5 rounded-l-none px-2 text-xs"
        >
          <Network className="size-3.5" aria-hidden="true" />
          Communication
        </Button>
      </div>

      <div className="mx-1 h-5 w-px bg-border" />

      <Button
        variant="ghost"
        size="sm"
        onClick={onFitView}
        aria-label="Fit to view"
        className="size-7 p-0"
      >
        <Maximize className="size-3.5" aria-hidden="true" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onZoomIn}
        aria-label="Zoom in"
        className="size-7 p-0"
      >
        <ZoomIn className="size-3.5" aria-hidden="true" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onZoomOut}
        aria-label="Zoom out"
        className="size-7 p-0"
      >
        <ZoomOut className="size-3.5" aria-hidden="true" />
      </Button>
    </div>
  )
}
