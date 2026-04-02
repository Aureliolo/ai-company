import { useCallback } from 'react'
import {
  ClipboardList,
  Download,
  GitBranch,
  Maximize,
  Merge,
  Redo2,
  Save,
  ShieldCheck,
  SplitSquareVertical,
  Undo2,
  UserCheck,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useReactFlow } from '@xyflow/react'
import { Button } from '@/components/ui/button'
import type { WorkflowNodeType } from '@/api/types'

interface NodePaletteItem {
  type: WorkflowNodeType
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const NODE_PALETTE: readonly NodePaletteItem[] = [
  { type: 'task', label: 'Task', icon: ClipboardList },
  { type: 'agent_assignment', label: 'Agent', icon: UserCheck },
  { type: 'conditional', label: 'Condition', icon: GitBranch },
  { type: 'parallel_split', label: 'Split', icon: SplitSquareVertical },
  { type: 'parallel_join', label: 'Join', icon: Merge },
]

export interface WorkflowToolbarProps {
  onAddNode: (type: WorkflowNodeType) => void
  onUndo: () => void
  onRedo: () => void
  onSave: () => void
  onValidate: () => void
  onExport: () => void
  canUndo: boolean
  canRedo: boolean
  dirty: boolean
  saving: boolean
  validating: boolean
  validationValid: boolean | null
}

export function WorkflowToolbar({
  onAddNode,
  onUndo,
  onRedo,
  onSave,
  onValidate,
  onExport,
  canUndo,
  canRedo,
  dirty,
  saving,
  validating,
  validationValid,
}: WorkflowToolbarProps) {
  const { fitView, zoomIn, zoomOut } = useReactFlow()

  const handleFitView = useCallback(() => fitView({ padding: 0.2 }), [fitView])

  return (
    <div className="flex items-center gap-1 rounded-lg border border-border bg-surface px-2 py-1">
      {/* Node palette */}
      <div className="flex items-center gap-0.5 border-r border-border pr-2">
        {NODE_PALETTE.map(({ type, label, icon: Icon }) => (
          <Button
            key={type}
            variant="ghost"
            size="sm"
            title={`Add ${label}`}
            aria-label={`Add ${label} node`}
            onClick={() => onAddNode(type)}
            className="size-8 p-0"
          >
            <Icon className="size-4" aria-hidden="true" />
          </Button>
        ))}
      </div>

      {/* Undo/Redo */}
      <div className="flex items-center gap-0.5 border-r border-border pr-2">
        <Button
          variant="ghost"
          size="sm"
          title="Undo"
          aria-label="Undo"
          onClick={onUndo}
          disabled={!canUndo}
          className="size-8 p-0"
        >
          <Undo2 className="size-4" aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          title="Redo"
          aria-label="Redo"
          onClick={onRedo}
          disabled={!canRedo}
          className="size-8 p-0"
        >
          <Redo2 className="size-4" aria-hidden="true" />
        </Button>
      </div>

      {/* Zoom */}
      <div className="flex items-center gap-0.5 border-r border-border pr-2">
        <Button variant="ghost" size="sm" title="Zoom In" aria-label="Zoom in" onClick={() => zoomIn()} className="size-8 p-0">
          <ZoomIn className="size-4" aria-hidden="true" />
        </Button>
        <Button variant="ghost" size="sm" title="Zoom Out" aria-label="Zoom out" onClick={() => zoomOut()} className="size-8 p-0">
          <ZoomOut className="size-4" aria-hidden="true" />
        </Button>
        <Button variant="ghost" size="sm" title="Fit View" aria-label="Fit view" onClick={handleFitView} className="size-8 p-0">
          <Maximize className="size-4" aria-hidden="true" />
        </Button>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          title="Validate"
          aria-label="Validate workflow"
          onClick={onValidate}
          disabled={validating}
          className="gap-1.5"
        >
          <ShieldCheck className="size-4" aria-hidden="true" />
          <span className="text-xs">Validate</span>
          {validationValid !== null && (
            <span className={validationValid ? 'text-success' : 'text-danger'}>
              {validationValid ? '\u2713' : '\u2717'}
            </span>
          )}
        </Button>

        <Button
          variant="ghost"
          size="sm"
          title="Export YAML"
          aria-label="Export as YAML"
          onClick={onExport}
          className="gap-1.5"
        >
          <Download className="size-4" aria-hidden="true" />
          <span className="text-xs">Export</span>
        </Button>

        <Button
          variant="default"
          size="sm"
          title="Save"
          aria-label="Save workflow"
          onClick={onSave}
          disabled={!dirty || saving}
          className="gap-1.5"
        >
          <Save className="size-4" aria-hidden="true" />
          <span className="text-xs">{saving ? 'Saving...' : 'Save'}</span>
        </Button>
      </div>
    </div>
  )
}
