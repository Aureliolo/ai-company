import { Monitor, Terminal } from 'lucide-react'
import { useBreakpoint } from '@/hooks/useBreakpoint'

/**
 * Full-screen overlay shown at mobile viewports (<768px).
 *
 * Renders nothing at desktop/tablet breakpoints. Self-manages
 * visibility via the useBreakpoint hook -- mount unconditionally.
 */
export function MobileUnsupportedOverlay() {
  const { isMobile } = useBreakpoint()

  if (!isMobile) return null

  return (
    <div
      role="alert"
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-background p-8 text-center"
    >
      <Monitor className="size-16 text-muted-foreground" strokeWidth={1} aria-hidden="true" />

      <div className="space-y-2">
        <h1 className="text-lg font-semibold text-foreground">
          Desktop Required
        </h1>
        <p className="max-w-xs text-sm text-text-secondary">
          This dashboard is designed for desktop browsers. Resize your window or use a larger screen.
        </p>
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-3">
        <Terminal className="size-4 text-accent" aria-hidden="true" />
        <code className="font-mono text-xs text-foreground">synthorg status</code>
      </div>

      <p className="text-xs text-muted-foreground">
        For mobile access, use the SynthOrg CLI
      </p>
    </div>
  )
}
