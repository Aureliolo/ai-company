import { Check, X, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ProviderPreset, ProbePresetResponse } from '@/api/types'

interface ProbeResultItemProps {
  preset: ProviderPreset
  result: ProbePresetResponse | undefined
  probing: boolean
  onAddPreset: (presetName: string) => void
}

function ProbeResultItem({ preset, result, probing, onAddPreset }: ProbeResultItemProps) {
  const detected = result && result.url !== null

  return (
    <div className="flex items-center gap-3 text-sm">
      {probing && !result ? (
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      ) : detected ? (
        <Check className="size-4 text-success" />
      ) : (
        <X className="size-4 text-muted-foreground" />
      )}
      <div className="flex-1">
        <span className="font-medium text-foreground">{preset.display_name}</span>
        {detected && result && (
          <span className="ml-2 text-xs text-muted-foreground">
            at {result.url} ({result.model_count} models)
          </span>
        )}
        {!probing && !detected && (
          <span className="ml-2 text-xs text-muted-foreground">Not found</span>
        )}
      </div>
      {detected && (
        <Button size="xs" onClick={() => onAddPreset(preset.name)}>
          Add
        </Button>
      )}
    </div>
  )
}

export interface ProviderProbeResultsProps {
  presets: readonly ProviderPreset[]
  probeResults: Readonly<Partial<Record<string, ProbePresetResponse>>>
  probing: boolean
  onAddPreset: (presetName: string) => void
}

export function ProviderProbeResults({
  presets,
  probeResults,
  probing,
  onAddPreset,
}: ProviderProbeResultsProps) {
  const localPresets = presets.filter((p) => p.auth_type === 'none')

  if (localPresets.length === 0) return null

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">
          {probing ? 'Detecting local providers...' : 'Auto-detected Providers'}
        </h3>
        <p className="text-xs text-muted-foreground">
          Checking for locally running LLM providers.
        </p>
      </div>
      {localPresets.map((preset) => (
        <ProbeResultItem
          key={preset.name}
          preset={preset}
          result={probeResults[preset.name]}
          probing={probing}
          onAddPreset={onAddPreset}
        />
      ))}
    </div>
  )
}
