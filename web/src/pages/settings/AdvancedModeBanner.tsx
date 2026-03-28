import { ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface AdvancedModeBannerProps {
  onDisable: () => void
}

export function AdvancedModeBanner({ onDisable }: AdvancedModeBannerProps) {
  return (
    <div
      role="status"
      className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning"
    >
      <ShieldAlert className="size-4 shrink-0" aria-hidden />
      <span className="flex-1">
        Advanced mode is active. Some settings may affect system stability.
      </span>
      <Button variant="ghost" size="xs" onClick={onDisable}>
        Disable
      </Button>
    </div>
  )
}
