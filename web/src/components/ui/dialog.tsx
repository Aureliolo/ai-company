import { Dialog as BaseDialog } from '@base-ui/react/dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

export interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  return (
    <BaseDialog.Root open={open} onOpenChange={onOpenChange}>
      {children}
    </BaseDialog.Root>
  )
}

export interface DialogContentProps {
  className?: string
  children: React.ReactNode
}

export function DialogContent({ className, children }: DialogContentProps) {
  return (
    <BaseDialog.Portal>
      <BaseDialog.Backdrop
        className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm transition-opacity duration-200 ease-out data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0"
      />
      <BaseDialog.Popup
        className={cn(
          'fixed top-1/2 left-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2',
          'rounded-xl border border-border bg-background shadow-[var(--so-shadow-card-hover)]',
          'max-h-[80vh] overflow-hidden',
          'transition-[opacity,translate,scale] duration-200 ease-out',
          'data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0',
          'data-[closed]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:scale-95',
          className,
        )}
      >
        {children}
      </BaseDialog.Popup>
    </BaseDialog.Portal>
  )
}

export interface DialogHeaderProps {
  className?: string
  children: React.ReactNode
}

export function DialogHeader({ className, children }: DialogHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between border-b border-border p-card', className)}>
      {children}
    </div>
  )
}

export interface DialogTitleProps {
  className?: string
  children: React.ReactNode
}

export function DialogTitle({ className, children }: DialogTitleProps) {
  return (
    <BaseDialog.Title className={cn('text-lg font-semibold text-foreground', className)}>
      {children}
    </BaseDialog.Title>
  )
}

export interface DialogDescriptionProps {
  className?: string
  children: React.ReactNode
}

export function DialogDescription({ className, children }: DialogDescriptionProps) {
  return (
    <BaseDialog.Description className={cn('text-sm text-muted-foreground', className)}>
      {children}
    </BaseDialog.Description>
  )
}

export interface DialogCloseButtonProps {
  className?: string
}

export function DialogCloseButton({ className }: DialogCloseButtonProps) {
  return (
    <BaseDialog.Close
      render={
        <Button
          // Explicit type="button" so a dialog wrapping a <form> does not
          // accidentally submit the form when the close icon is clicked.
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Close"
          className={className}
        >
          <X className="size-4" />
        </Button>
      }
    />
  )
}
