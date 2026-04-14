import { useCallback, useEffect, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'motion/react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { createLogger } from '@/lib/logger'
import { springDefault, tweenExitFast, tweenFast } from '@/lib/motion'

const log = createLogger('Drawer')

interface DrawerPropsBase {
  open: boolean
  onClose: () => void
  /** Which edge the drawer slides in from. @default 'right' */
  side?: 'left' | 'right'
  /** Additional class names merged into the content wrapper (e.g. `"p-0"` to remove default padding). */
  contentClassName?: string
  children: React.ReactNode
  className?: string
}

/**
 * At least one of `title` or `ariaLabel` must be provided so the dialog
 * always has an accessible name (WAI-ARIA dialog pattern). When `title` is
 * provided the Drawer renders a built-in header; when omitted, the header is
 * skipped and `ariaLabel` supplies the accessible name instead.
 */
export type DrawerProps = DrawerPropsBase & (
  | { /** Visible header title. */ title: string; /** Explicit aria-label; when omitted, `title` is used as the accessible name. */ ariaLabel?: string }
  | { title?: undefined; /** Explicit aria-label (required when title is omitted). */ ariaLabel: string }
)

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

function getPanelVariants(side: 'left' | 'right') {
  const offscreen = side === 'left' ? '-100%' : '100%'
  return {
    hidden: { x: offscreen },
    visible: { x: 0, transition: springDefault },
    exit: { x: offscreen, transition: tweenExitFast },
  }
}

export function Drawer({ open, onClose, title, ariaLabel, side = 'right', contentClassName, children, className }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const openerRef = useRef<Element | null>(null)
  const panelVariants = useMemo(() => getPanelVariants(side), [side])

  // Trim once, reuse for accessible name and header rendering
  const trimmedTitle = title?.trim() || undefined
  const accessibleName = ariaLabel?.trim() || trimmedTitle || undefined

  useEffect(() => {
    if (process.env.NODE_ENV !== 'production' && !accessibleName) {
      log.warn('Either `title` or `ariaLabel` must be a non-empty string for accessible dialog naming.')
    }
  }, [accessibleName])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose],
  )

  useEffect(() => {
    if (!open) return
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, handleKeyDown])

  // Save opener, move initial focus to panel, and trap Tab cycling within it
  useEffect(() => {
    if (!open || !panelRef.current) return
    openerRef.current = document.activeElement
    panelRef.current.focus()

    const panel = panelRef.current
    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const focusable = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"]), [contenteditable]:not([contenteditable="false"])',
      )
      if (focusable.length === 0) {
        // No focusable children (e.g. headerless drawer with text-only content) --
        // keep focus on the panel itself so Tab cannot escape the modal.
        e.preventDefault()
        panel.focus()
        return
      }
      const first = focusable[0]!
      const last = focusable[focusable.length - 1]!
      const active = document.activeElement
      const outsideOrPanel = active === panel || !panel.contains(active)
      if (e.shiftKey && (active === first || outsideOrPanel)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && (active === last || outsideOrPanel)) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleTab)
    return () => {
      document.removeEventListener('keydown', handleTab)
      // Restore focus to the element that opened the drawer
      if (openerRef.current instanceof HTMLElement) {
        openerRef.current.focus()
      }
      openerRef.current = null
    }
  }, [open])

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Overlay */}
          <motion.div
            variants={overlayVariants}
            initial="hidden"
            animate="visible"
            exit="hidden"
            transition={tweenFast}
            className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
            data-testid="drawer-overlay"
          />
          {/* Panel */}
          <motion.div
            ref={panelRef}
            variants={panelVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            role="dialog"
            aria-modal="true"
            aria-label={accessibleName}
            tabIndex={-1}
            className={cn(
              'fixed inset-y-0 z-50 flex w-[40vw] min-w-80 max-w-xl flex-col',
              side === 'left' ? 'left-0 border-r' : 'right-0 border-l',
              'border-border bg-card shadow-[var(--so-shadow-card-hover)]',
              className,
            )}
          >
            {/* Header (omitted when title is absent or whitespace-only) */}
            {trimmedTitle && (
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <h2 className="text-sm font-semibold text-foreground">{trimmedTitle}</h2>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close"
                  className={cn(
                    'rounded-md p-1 text-muted-foreground transition-colors',
                    'hover:bg-card-hover hover:text-foreground',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
                  )}
                >
                  <X className="size-4" />
                </button>
              </div>
            )}
            {/* Content */}
            <div data-testid="drawer-content" className={cn('flex-1 overflow-y-auto p-4', contentClassName)}>
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body,
  )
}
