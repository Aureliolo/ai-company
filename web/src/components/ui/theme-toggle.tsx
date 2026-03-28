import { Palette } from 'lucide-react'
import { Popover } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { SelectField } from '@/components/ui/select-field'
import { SegmentedControl } from '@/components/ui/segmented-control'
import {
  useThemeStore,
  COLOR_PALETTES,
  DENSITIES,
  TYPOGRAPHIES,
  ANIMATION_PRESETS,
  SIDEBAR_MODES,
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

const COLOR_LABELS: Record<ColorPalette, string> = {
  'warm-ops': 'Warm Ops',
  'ice-station': 'Ice Station',
  stealth: 'Stealth',
  signal: 'Signal',
  neon: 'Neon',
}

const DENSITY_LABELS: Record<Density, string> = {
  dense: 'Dense',
  balanced: 'Balanced',
  medium: 'Medium',
  sparse: 'Sparse',
}

const TYPOGRAPHY_LABELS: Record<Typography, string> = {
  geist: 'Geist',
  jetbrains: 'JetBrains + Inter',
  'ibm-plex': 'IBM Plex',
}

const ANIMATION_LABELS: Record<AnimationPreset, string> = {
  minimal: 'Minimal',
  spring: 'Spring',
  instant: 'Instant',
  'status-driven': 'Status',
  aggressive: 'Aggro',
}

const SIDEBAR_LABELS: Record<SidebarMode, string> = {
  rail: 'Rail',
  collapsible: 'Collapse',
  hidden: 'Hidden',
  persistent: 'Persist',
  compact: 'Compact',
}

const COLOR_OPTIONS = COLOR_PALETTES.map((v) => ({ value: v, label: COLOR_LABELS[v] }))
const DENSITY_OPTIONS = DENSITIES.map((v) => ({ value: v, label: DENSITY_LABELS[v] }))
const TYPOGRAPHY_OPTIONS = TYPOGRAPHIES.map((v) => ({ value: v, label: TYPOGRAPHY_LABELS[v] }))
const ANIMATION_OPTIONS = ANIMATION_PRESETS.map((v) => ({ value: v, label: ANIMATION_LABELS[v] }))
const SIDEBAR_OPTIONS = SIDEBAR_MODES.map((v) => ({ value: v, label: SIDEBAR_LABELS[v] }))

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
              options={COLOR_OPTIONS}
              value={colorPalette}
              onChange={(v) => setColorPalette(v as ColorPalette)}
            />

            {/* Density */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Density</span>
              <SegmentedControl<Density>
                label="Density"
                options={DENSITY_OPTIONS}
                value={density}
                onChange={setDensity}
              />
            </div>

            {/* Typography */}
            <SelectField
              label="Font"
              options={TYPOGRAPHY_OPTIONS}
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
              <SegmentedControl<AnimationPreset>
                label="Animation"
                options={ANIMATION_OPTIONS}
                value={animation}
                onChange={setAnimation}
              />
            </div>

            {/* Sidebar mode */}
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Sidebar</span>
              <SegmentedControl<SidebarMode>
                label="Sidebar mode"
                options={SIDEBAR_OPTIONS}
                value={sidebarMode}
                onChange={setSidebarMode}
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
