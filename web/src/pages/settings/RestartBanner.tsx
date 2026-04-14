import { AnimatePresence, motion } from 'motion/react'
import { springDefault } from '@/lib/motion'
import { AlertTriangle, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface RestartBannerProps {
  count: number
  onDismiss: () => void
}

export function RestartBanner({ count, onDismiss }: RestartBannerProps) {
  const message = count === 1
    ? '1 setting requires a restart to take effect.'
    : `${count} settings require a restart to take effect.`

  return (
    <AnimatePresence>
      {count > 0 && (
        <motion.div
          key="restart-banner"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={springDefault}
          className="flex items-center gap-3 rounded-lg border border-warning/30 bg-warning/5 p-card"
          role="alert"
        >
          <AlertTriangle className="size-4 shrink-0 text-warning" aria-hidden />
          <span className="flex-1 text-sm text-warning">{message}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDismiss}
            aria-label="Dismiss"
            className="text-warning hover:text-warning"
          >
            <X className="size-3.5" aria-hidden />
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
