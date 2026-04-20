import { validateWorkflowDraft } from '@/api/endpoints/workflows'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type { SliceCreator, ValidationSlice } from './types'

const log = createLogger('workflow-editor:validation')

export const createValidationSlice: SliceCreator<ValidationSlice> = (set, get) => ({
  validationResult: null,
  validating: false,

  validate: async () => {
    const { definition, nodes, edges } = get()
    if (!definition) {
      set({ error: 'Cannot validate: no workflow loaded' })
      return
    }
    const badNodes = nodes.filter((n) => !n.type)
    const badEdges = edges.filter((e) => !(e.data as Record<string, unknown>)?.edgeType)
    if (badNodes.length > 0 || badEdges.length > 0) {
      const parts: string[] = []
      if (badNodes.length > 0) parts.push(`nodes missing type: ${badNodes.map((n) => n.id).join(', ')}`)
      if (badEdges.length > 0) parts.push(`edges missing type: ${badEdges.map((e) => e.id).join(', ')}`)
      set({
        error: `Cannot validate -- ${parts.join('; ')}. Remove and re-add the affected items.`,
        validating: false,
      })
      return
    }

    set({ validating: true })
    try {
      const result = await validateWorkflowDraft({
        name: definition.name,
        workflow_type: definition.workflow_type,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type!,
          label: (n.data as Record<string, unknown>)?.label ?? n.id,
          position_x: n.position.x,
          position_y: n.position.y,
          config: ((n.data as Record<string, unknown>)?.config as Record<string, unknown>) ?? {},
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source_node_id: e.source,
          target_node_id: e.target,
          type: ((e.data as Record<string, unknown>)?.edgeType as string) ?? 'sequential',
          label: (e.label as string) ?? null,
        })),
      })
      set({ validationResult: result, validating: false })
    } catch (err) {
      log.warn('Workflow validation failed', sanitizeForLog(err))
      set({ validating: false, validationResult: null, error: getErrorMessage(err) })
    }
  },
})
