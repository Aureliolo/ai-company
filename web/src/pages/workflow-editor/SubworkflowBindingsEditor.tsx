import { useEffect, useState } from 'react'
import { InputField } from '@/components/ui/input-field'
import { Skeleton } from '@/components/ui/skeleton'
import { getVersion } from '@/api/endpoints/subworkflows'
import { createLogger } from '@/lib/logger'
import { sanitizeForLog } from '@/utils/logging'
import type { WorkflowIODeclaration } from '@/api/types'

const log = createLogger('SubworkflowBindingsEditor')

interface SubworkflowBindingsEditorProps {
  subworkflowId: string
  version: string
  inputBindings: Record<string, unknown>
  outputBindings: Record<string, unknown>
  onInputBindingsChange: (bindings: Record<string, unknown>) => void
  onOutputBindingsChange: (bindings: Record<string, unknown>) => void
}

export function SubworkflowBindingsEditor({
  subworkflowId,
  version,
  inputBindings,
  outputBindings,
  onInputBindingsChange,
  onOutputBindingsChange,
}: SubworkflowBindingsEditorProps) {
  const [inputs, setInputs] = useState<readonly WorkflowIODeclaration[]>([])
  const [outputs, setOutputs] = useState<readonly WorkflowIODeclaration[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!subworkflowId || !version) return
    let cancelled = false
    async function load() {
      setInputs([])
      setOutputs([])
      setLoading(true)
      try {
        const def = await getVersion(subworkflowId, version)
        if (!cancelled) {
          setInputs(def.inputs)
          setOutputs(def.outputs)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          log.warn('Failed to load subworkflow IO declarations', sanitizeForLog(err))
          setInputs([])
          setOutputs([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [subworkflowId, version])

  if (loading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading bindings">
        <Skeleton className="h-8 rounded" />
        <Skeleton className="h-8 rounded" />
      </div>
    )
  }

  if (inputs.length === 0 && outputs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        This subworkflow has no declared inputs or outputs.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-section-gap">
      {inputs.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-medium text-foreground">
            Input Bindings
          </h4>
          <div className="flex flex-col gap-2">
            {inputs.map((decl) => (
              <InputField
                key={decl.name}
                label={`${decl.name} (${decl.type}${decl.required ? '' : ', optional'})`}
                value={String(inputBindings[decl.name] ?? '')}
                onValueChange={(v) =>
                  onInputBindingsChange({ ...inputBindings, [decl.name]: v })
                }
                placeholder={
                  decl.required
                    ? '@parent.variable or literal'
                    : `default: ${String(decl.default ?? 'none')}`
                }
                hint={decl.description || undefined}
              />
            ))}
          </div>
        </div>
      )}

      {outputs.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-medium text-foreground">
            Output Bindings
          </h4>
          <div className="flex flex-col gap-2">
            {outputs.map((decl) => (
              <InputField
                key={decl.name}
                label={`${decl.name} (${decl.type})`}
                value={String(outputBindings[decl.name] ?? '')}
                onValueChange={(v) =>
                  onOutputBindingsChange({ ...outputBindings, [decl.name]: v })
                }
                placeholder="@child.variable"
                hint={decl.description || undefined}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
