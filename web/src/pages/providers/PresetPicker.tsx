import { Server } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ProviderPreset } from '@/api/types'

interface PresetPickerProps {
  presets: readonly ProviderPreset[]
  selected: string | null
  onSelect: (presetName: string | null) => void
  loading?: boolean
}

export function PresetPicker({ presets, selected, onSelect, loading }: PresetPickerProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-3 max-[767px]:grid-cols-2">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-lg border border-border bg-bg-surface" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-3 max-[767px]:grid-cols-2">
      {presets.map((preset) => (
        <button
          key={preset.name}
          type="button"
          aria-pressed={selected === preset.name}
          aria-label={`Select ${preset.display_name} preset`}
          onClick={() => onSelect(preset.name === selected ? null : preset.name)}
          className={cn(
            'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition-all duration-150',
            'hover:bg-card-hover hover:border-bright',
            selected === preset.name
              ? 'border-accent bg-accent/5'
              : 'border-border bg-card',
          )}
        >
          <Server className="size-5 text-text-secondary" />
          <span className="text-sm font-medium text-foreground">
            {preset.display_name}
          </span>
          <span className="text-xs text-text-muted line-clamp-1">
            {preset.description}
          </span>
        </button>
      ))}

      {/* Custom option */}
      <button
        type="button"
        aria-pressed={selected === '__custom__'}
        aria-label="Select custom provider"
        onClick={() => onSelect(selected === '__custom__' ? null : '__custom__')}
        className={cn(
          'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition-all duration-150',
          'hover:bg-card-hover hover:border-bright',
          selected === '__custom__'
            ? 'border-accent bg-accent/5'
            : 'border-border border-dashed bg-card',
        )}
      >
        <Server className="size-5 text-text-muted" />
        <span className="text-sm font-medium text-foreground">Custom</span>
        <span className="text-xs text-text-muted">Any endpoint</span>
      </button>
    </div>
  )
}
