import { useState } from 'react'
import { createLogger } from '@/lib/logger'
import { Check, X, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ProbePresetResponse, ProviderConfig, ProviderPreset } from '@/api/types/providers'

const log = createLogger('setup')

interface ProbeResultItemProps {
  preset: ProviderPreset
  result: ProbePresetResponse | undefined
  probing: boolean
  alreadyAdded: boolean
  adding: boolean
  onAddPreset: (presetName: string, detectedUrl?: string) => void
}

function ProbeResultItem({ preset, result, probing, alreadyAdded, adding, onAddPreset }: ProbeResultItemProps) {
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
      {detected && !alreadyAdded && (
        <Button
          size="xs"
          onClick={() => onAddPreset(preset.name, result?.url ?? undefined)}
          disabled={adding}
        >
          {adding ? 'Adding...' : 'Add'}
        </Button>
      )}
      {detected && alreadyAdded && (
        <span className="text-xs text-success">Added</span>
      )}
    </div>
  )
}

export interface ProviderProbeResultsProps {
  presets: readonly ProviderPreset[]
  probeResults: Readonly<Partial<Record<string, ProbePresetResponse>>>
  probing: boolean
  providers: Readonly<Record<string, ProviderConfig>>
  onAddPreset: (presetName: string, detectedUrl?: string) => Promise<void>
  onReprobe: () => Promise<void>
}

export function ProviderProbeResults({
  presets,
  probeResults,
  probing,
  providers,
  onAddPreset,
  onReprobe,
}: ProviderProbeResultsProps) {
  const [addingPreset, setAddingPreset] = useState<string | null>(null)

  const localPresets = presets.filter((p) => p.auth_type === 'none')

  if (localPresets.length === 0) return null

  const handleAdd = async (presetName: string, detectedUrl?: string) => {
    setAddingPreset(presetName)
    try {
      await onAddPreset(presetName, detectedUrl)
    } catch (err) {
      // Expected: store sets providersError before re-throwing.
      // Log unexpected errors for debugging.
      log.error('Add preset failed:', err)
    } finally {
      setAddingPreset(null)
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-card">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">
            {probing ? 'Detecting local providers...' : 'Auto-detected Providers'}
          </h3>
          <p className="text-xs text-muted-foreground">
            Checking for locally running LLM providers.
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => void onReprobe()}
          disabled={probing}
          aria-label="Re-scan local providers"
        >
          <RefreshCw className={probing ? 'size-3.5 animate-spin' : 'size-3.5'} />
        </Button>
      </div>
      {localPresets.map((preset) => {
        const probeResult = probeResults[preset.name]
        return (
          <ProbeResultItem
            key={preset.name}
            preset={preset}
            result={probeResult}
            probing={probing}
            alreadyAdded={preset.name in providers}
            adding={addingPreset === preset.name}
            onAddPreset={handleAdd}
          />
        )
      })}
    </div>
  )
}
