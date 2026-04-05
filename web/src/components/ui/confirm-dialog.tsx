import { AlertDialog } from '@base-ui/react/alert-dialog'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { createLogger } from '@/lib/logger'
import { Button } from './button'

const log = createLogger('ConfirmDialog')

export interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  /** Label for the confirm button (default: "Confirm"). */
  confirmLabel?: string
  /** Label for the cancel button (default: "Cancel"). */
  cancelLabel?: string
  /** Visual variant (default: "default"). "destructive" uses a red confirm button. */
  variant?: 'default' | 'destructive'
  onConfirm: () => void | Promise<void>
  /** Whether the confirm action is in progress. */
  loading?: boolean
  className?: string
  /** Optional content rendered between description and action buttons. */
  children?: React.ReactNode
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  loading = false,
  className,
  children,
}: ConfirmDialogProps) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Backdrop
          className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm transition-opacity duration-200 ease-out data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0"
        />
        <AlertDialog.Popup
          className={cn(
            'fixed top-1/2 left-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2',
            'rounded-xl border border-border-bright bg-surface p-card shadow-lg',
            'transition-[opacity,translate,scale] duration-200 ease-out',
            'data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0',
            'data-[closed]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:scale-95',
            className,
          )}
        >
          <AlertDialog.Title className="text-base font-semibold text-foreground">
            {title}
          </AlertDialog.Title>
          {description && (
            <AlertDialog.Description className="mt-2 text-sm text-muted-foreground">
              {description}
            </AlertDialog.Description>
          )}
          {children}
          <div className="mt-6 flex justify-end gap-3">
            <AlertDialog.Close
              render={
                <Button variant="outline" disabled={loading}>
                  {cancelLabel}
                </Button>
              }
            />
            <Button
              variant={variant === 'destructive' ? 'destructive' : 'default'}
              data-variant={variant}
              disabled={loading}
              onClick={async () => {
                try {
                  await onConfirm()
                  onOpenChange(false)
                } catch (err) {
                  // Dialog stays open on error so the caller can retry from
                  // the same surface. Log the cause so the failure is not
                  // invisible if the caller forgets to toast its own error.
                  log.warn('ConfirmDialog onConfirm threw', { title }, err)
                }
              }}
            >
              {loading && (
                <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />
              )}
              {confirmLabel}
            </Button>
          </div>
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
