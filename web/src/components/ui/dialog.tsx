import { Dialog as RadixDialog } from 'radix-ui'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      {children}
    </RadixDialog.Root>
  )
}

export interface DialogContentProps {
  className?: string
  children: React.ReactNode
}

export function DialogContent({ className, children }: DialogContentProps) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay
        className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
      />
      <RadixDialog.Content
        className={cn(
          'fixed top-1/2 left-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2',
          'rounded-xl border border-border bg-background shadow-lg',
          'max-h-[80vh] overflow-hidden',
          'data-[state=open]:animate-in data-[state=closed]:animate-out',
          'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
          'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          className,
        )}
      >
        {children}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  )
}

export interface DialogHeaderProps {
  className?: string
  children: React.ReactNode
}

export function DialogHeader({ className, children }: DialogHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between border-b border-border px-6 py-4', className)}>
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
    <RadixDialog.Title className={cn('text-lg font-semibold text-foreground', className)}>
      {children}
    </RadixDialog.Title>
  )
}

export interface DialogDescriptionProps {
  className?: string
  children: React.ReactNode
}

export function DialogDescription({ className, children }: DialogDescriptionProps) {
  return (
    <RadixDialog.Description className={cn('text-sm text-muted', className)}>
      {children}
    </RadixDialog.Description>
  )
}

export interface DialogCloseButtonProps {
  className?: string
}

export function DialogCloseButton({ className }: DialogCloseButtonProps) {
  return (
    <RadixDialog.Close asChild>
      <button
        type="button"
        aria-label="Close"
        className={cn(
          'rounded-md p-1 text-muted-foreground transition-colors',
          'hover:bg-card-hover hover:text-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
          className,
        )}
      >
        <X className="size-4" />
      </button>
    </RadixDialog.Close>
  )
}
