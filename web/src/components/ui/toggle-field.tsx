import { useId } from 'react'
import { cn } from '@/lib/utils'

export interface ToggleFieldProps {
  label: string
  description?: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

export function ToggleField({
  label,
  description,
  checked,
  onChange,
  disabled,
  className,
}: ToggleFieldProps) {
  const id = useId()

  return (
    <div className={cn('flex items-start gap-3', className)}>
      <button
        id={id}
        role="switch"
        type="button"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        disabled={disabled}
        className={cn(
          'relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          'disabled:opacity-60 disabled:cursor-not-allowed',
          checked ? 'bg-accent' : 'bg-border',
        )}
      >
        <span
          className={cn(
            'block h-4 w-4 rounded-full bg-foreground transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0.5',
          )}
        />
      </button>
      <div className="flex flex-col gap-0.5">
        <label htmlFor={id} className={cn('text-sm font-medium', disabled ? 'cursor-default text-muted-foreground' : 'cursor-pointer text-foreground')}>
          {label}
        </label>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
    </div>
  )
}
