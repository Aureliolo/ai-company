import { AlertDialog } from 'radix-ui'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

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
}: ConfirmDialogProps) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay
          className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
        />
        <AlertDialog.Content
          className={cn(
            'fixed top-1/2 left-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2',
            'rounded-xl border border-border-bright bg-surface p-6 shadow-lg',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
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
          <div className="mt-6 flex justify-end gap-3">
            <AlertDialog.Cancel asChild>
              <Button variant="outline" disabled={loading}>
                {cancelLabel}
              </Button>
            </AlertDialog.Cancel>
            <Button
              variant={variant === 'destructive' ? 'destructive' : 'default'}
              disabled={loading}
              onClick={async (e) => {
                e.preventDefault()
                try {
                  await onConfirm()
                  onOpenChange(false)
                } catch {
                  // Dialog stays open on error -- caller can surface the error.
                }
              }}
            >
              {loading && (
                <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />
              )}
              {confirmLabel}
            </Button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
