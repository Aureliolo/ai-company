import { useId, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { LazyCodeMirrorEditor } from '@/components/ui/lazy-code-mirror-editor'

export interface WorkflowYamlPreviewProps {
  yaml: string
}

export function WorkflowYamlPreview({ yaml }: WorkflowYamlPreviewProps) {
  const [collapsed, setCollapsed] = useState(false)
  const previewContentId = useId()

  return (
    <div className="flex flex-col border-t border-border bg-surface">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        aria-expanded={!collapsed}
        aria-controls={previewContentId}
        aria-label={collapsed ? 'Expand YAML preview' : 'Collapse YAML preview'}
      >
        {collapsed ? (
          <ChevronUp className="size-3.5" aria-hidden="true" />
        ) : (
          <ChevronDown className="size-3.5" aria-hidden="true" />
        )}
        YAML Preview
      </button>

      {!collapsed && (
        <div id={previewContentId} className="h-48 overflow-auto border-t border-border">
          <LazyCodeMirrorEditor
            value={yaml}
            language="yaml"
            onChange={() => {}}
            readOnly
          />
        </div>
      )}
    </div>
  )
}
