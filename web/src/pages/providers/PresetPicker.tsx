import { Server } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ProviderPreset } from '@/api/types/providers'

interface PresetOptionCardProps {
  name: string
  displayName: string
  description: string
  selected: boolean
  onClick: () => void
  ariaLabel: string
  dashed?: boolean
  iconMuted?: boolean
}

function PresetOptionCard({
  displayName,
  description,
  selected,
  onClick,
  ariaLabel,
  dashed = false,
  iconMuted = false,
}: PresetOptionCardProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={ariaLabel}
      onClick={onClick}
      className={cn(
        'flex flex-col items-center gap-2 rounded-lg border p-card text-center transition-all duration-150',
        'hover:bg-card-hover hover:border-bright',
        selected
          ? 'border-accent bg-accent/5'
          : cn('border-border bg-card', dashed && 'border-dashed'),
      )}
    >
      <Server className={cn('size-6', iconMuted ? 'text-text-muted' : 'text-text-secondary')} />
      <span className="text-sm font-medium text-foreground">{displayName}</span>
      <span className="text-xs text-text-muted line-clamp-2">{description}</span>
    </button>
  )
}

interface PresetPickerProps {
  presets: readonly ProviderPreset[]
  selected: string | null
  onSelect: (presetName: string | null) => void
  loading?: boolean
}

export function PresetPicker({ presets, selected, onSelect, loading }: PresetPickerProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-grid-gap max-[767px]:grid-cols-2">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg border border-border bg-bg-surface" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-grid-gap max-[767px]:grid-cols-2">
      {presets.map((preset) => (
        <PresetOptionCard
          key={preset.name}
          name={preset.name}
          displayName={preset.display_name}
          description={preset.description}
          selected={selected === preset.name}
          onClick={() => onSelect(preset.name === selected ? null : preset.name)}
          ariaLabel={`Select ${preset.display_name} preset`}
        />
      ))}

      <PresetOptionCard
        name="__custom__"
        displayName="Custom"
        description="Any endpoint"
        selected={selected === '__custom__'}
        onClick={() => onSelect(selected === '__custom__' ? null : '__custom__')}
        ariaLabel="Select custom provider"
        dashed
        iconMuted
      />
    </div>
  )
}
