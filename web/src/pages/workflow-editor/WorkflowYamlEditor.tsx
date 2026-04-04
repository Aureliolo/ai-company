/**
 * Bidirectional YAML editor for workflow definitions.
 *
 * Allows editing YAML directly and applying changes back to the
 * visual canvas. Shows inline parse/validation errors.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check } from 'lucide-react'
import { LazyCodeMirrorEditor } from '@/components/ui/lazy-code-mirror-editor'
import { Button } from '@/components/ui/button'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'
import { parseYamlToNodesEdges } from './yaml-to-nodes'
import type { Node } from '@xyflow/react'

interface WorkflowYamlEditorProps {
  initialYaml: string
}

export function WorkflowYamlEditor({ initialYaml }: WorkflowYamlEditorProps) {
  const [yamlText, setYamlText] = useState(initialYaml)
  const [parseErrors, setParseErrors] = useState<string[]>([])
  const [parseWarnings, setParseWarnings] = useState<string[]>([])
  const [applied, setApplied] = useState(false)
  const appliedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (appliedTimerRef.current !== null) clearTimeout(appliedTimerRef.current)
    }
  }, [])

  const handleApply = useCallback(() => {
    // Build position map from current nodes
    const currentNodes = useWorkflowEditorStore.getState().nodes
    const positionMap = new Map<string, { x: number; y: number }>()
    for (const node of currentNodes) {
      positionMap.set(node.id, node.position)
    }

    const result = parseYamlToNodesEdges(yamlText, positionMap)

    setParseErrors(result.errors)
    setParseWarnings(result.warnings)

    if (result.errors.length > 0) return

    // Apply to store
    const store = useWorkflowEditorStore.getState()
    const definition = store.definition
    if (!definition) return

    // Map nodes to ReactFlow format with proper data structure
    const mappedNodes: Node[] = result.nodes.map((n) => ({
      ...n,
      data: {
        ...((n.data ?? {}) as Record<string, unknown>),
        label: ((n.data as Record<string, unknown>)?.label as string) ?? n.id,
      },
    }))

    // Push undo snapshot and replace nodes/edges directly
    const snapshot = { nodes: structuredClone(store.nodes), edges: structuredClone(store.edges) }
    useWorkflowEditorStore.setState((s) => ({
      nodes: mappedNodes,
      edges: result.edges,
      dirty: true,
      yamlPreview: yamlText,
      undoStack: [...s.undoStack.slice(-49), snapshot],
      redoStack: [],
    }))

    setApplied(true)
    if (appliedTimerRef.current !== null) clearTimeout(appliedTimerRef.current)
    appliedTimerRef.current = setTimeout(() => {
      setApplied(false)
      appliedTimerRef.current = null
    }, 2000)
  }, [yamlText])

  const handleRevert = useCallback(() => {
    setYamlText(initialYaml)
    setParseErrors([])
    setParseWarnings([])
  }, [initialYaml])

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1">
        <LazyCodeMirrorEditor
          value={yamlText}
          onChange={setYamlText}
          language="yaml"
        />
      </div>

      {parseErrors.length > 0 && (
        <div className="border-t border-danger/30 bg-danger/5 p-card">
          <div className="flex items-center gap-1.5 text-sm font-medium text-danger">
            <AlertTriangle className="size-4" />
            {parseErrors.length} error{parseErrors.length !== 1 ? 's' : ''}
          </div>
          <ul className="mt-1 space-y-0.5 text-xs text-danger">
            {parseErrors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {parseWarnings.length > 0 && parseErrors.length === 0 && (
        <div className="border-t border-warning/30 bg-warning/5 p-card">
          <ul className="space-y-0.5 text-xs text-warning">
            {parseWarnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center justify-end gap-2 border-t border-border p-2">
        {applied && (
          <span className="flex items-center gap-1 text-xs text-success">
            <Check className="size-3" />
            Applied
          </span>
        )}
        <Button variant="outline" size="sm" onClick={handleRevert}>
          Revert
        </Button>
        <Button size="sm" onClick={handleApply}>
          Apply to Canvas
        </Button>
      </div>
    </div>
  )
}
