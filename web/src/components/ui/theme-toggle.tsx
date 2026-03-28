import { useMemo } from 'react'
import { Palette } from 'lucide-react'
import { Popover } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { SelectField } from '@/components/ui/select-field'
import { SegmentedControl } from '@/components/ui/segmented-control'
import {
  useThemeStore,
  type ColorPalette,
  type Density,
  type Typography,
  type AnimationPreset,
  type SidebarMode,
} from '@/stores/theme'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Option constants
// ---------------------------------------------------------------------------

const COLOR_OPTIONS = [
  { value: 'warm-ops', label: 'Warm Ops' },
  { value: 'ice-station', label: 'Ice Station' },
  { value: 'stealth', label: 'Stealth' },
  { value: 'signal', label: 'Signal' },
  { value: 'neon', label: 'Neon' },
] as const

const DENSITY_OPTIONS = [
  { value: 'dense', label: 'Dense' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'medium', label: 'Medium' },
  { value: 'sparse', label: 'Sparse' },
] as const

const TYPOGRAPHY_OPTIONS = [
  { value: 'geist', label: 'Geist' },
  { value: 'jetbrains', label: 'JetBrains + Inter' },
  { value: 'ibm-plex', label: 'IBM Plex' },
] as const

const ANIMATION_OPTIONS = [
  { value: 'minimal', label: 'Minimal' },
  { value: 'spring', label: 'Spring' },
  { value: 'instant', label: 'Instant' },
  { value: 'status-driven', label: 'Status' },
  { value: 'aggressive', label: 'Aggro' },
] as const

const SIDEBAR_OPTIONS = [
  { value: 'rail', label: 'Rail' },
  { value: 'collapsible', label: 'Collapse' },
  { value: 'hidden', label: 'Hidden' },
  { value: 'persistent', label: 'Persist' },
  { value: 'compact', label: 'Compact' },
] as const

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface ThemeToggleProps {
  className?: string
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const popoverOpen = useThemeStore((s) => s.popoverOpen)
  const setPopoverOpen = useThemeStore((s) => s.setPopoverOpen)
  const colorPalette = useThemeStore((s) => s.colorPalette)
  const density = useThemeStore((s) => s.density)
  const typography = useThemeStore((s) => s.typography)
  const animation = useThemeStore((s) => s.animation)
  const sidebarMode = useThemeStore((s) => s.sidebarMode)
  const reducedMotion = useThemeStore((s) => s.reducedMotionDetected)
  const setColorPalette = useThemeStore((s) => s.setColorPalette)
  const setDensity = useThemeStore((s) => s.setDensity)
  const setTypography = useThemeStore((s) => s.setTypography)
  const setAnimation = useThemeStore((s) => s.setAnimation)
  const setSidebarMode = useThemeStore((s) => s.setSidebarMode)
  const reset = useThemeStore((s) => s.reset)

  // Memoize stable option arrays for SegmentedControl (avoid re-renders)
  const densityOpts = useMemo(() => [...DENSITY_OPTIONS], [])
  const animationOpts = useMemo(() => [...ANIMATION_OPTIONS], [])
  const sidebarOpts = useMemo(() => [...SIDEBAR_OPTIONS], [])

  return (
    <Popover.Root open={popoverOpen} onOpenChange={setPopoverOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          title="Theme preferences"
          aria-label="Theme preferences"
          className={cn(
            'flex items-center text-muted-foreground transition-colors hover:text-foreground',
            className,
          )}
        >
          <Palette className="size-3.5" aria-hidden="true" />
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="end"
          sideOffset={8}
          className={cn(
            'z-50 w-80 rounded-xl border border-border-bright bg-surface p-4',
            'shadow-lg animate-in fade-in-0 zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
          )}
        >
          <h3 className="mb-3 text-sm font-semibold text-foreground">
            Theme Preferences
          </h3>

          <div className="space-y-4">
            {/* Color palette */}
            <SelectField
              label="Color"
              options={[...COLOR_OPTIONS]}
              value={colorPalette}
              onChange={(v) => setColorPalette(v as ColorPalette)}
            />

            {/* Density */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Density</span>
              <SegmentedControl
                label="Density"
                options={densityOpts}
                value={density}
                onChange={(v) => setDensity(v as Density)}
              />
            </div>

            {/* Typography */}
            <SelectField
              label="Font"
              options={[...TYPOGRAPHY_OPTIONS]}
              value={typography}
              onChange={(v) => setTypography(v as Typography)}
            />

            {/* Animation */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">
                Motion
                {reducedMotion && (
                  <span className="ml-1.5 text-xs font-normal text-warning">
                    (reduced motion)
                  </span>
                )}
              </span>
              <SegmentedControl
                label="Animation"
                options={animationOpts}
                value={animation}
                onChange={(v) => setAnimation(v as AnimationPreset)}
              />
            </div>

            {/* Sidebar mode */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Sidebar</span>
              <SegmentedControl
                label="Sidebar mode"
                options={sidebarOpts}
                value={sidebarMode}
                onChange={(v) => setSidebarMode(v as SidebarMode)}
              />
            </div>
          </div>

          {/* Reset */}
          <div className="mt-4 border-t border-border pt-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={reset}
              className="text-xs text-text-muted hover:text-foreground"
            >
              Reset to defaults
            </Button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
