import { useId } from 'react'
import { cn } from '@/lib/utils'

export interface InputFieldProps extends Omit<React.ComponentProps<'input'>, 'id'> {
  label: string
  error?: string | null
  hint?: string
  /** Render a textarea instead of input. */
  multiline?: boolean
  rows?: number
  ref?: React.Ref<HTMLInputElement>
}

export function InputField({
  label, error, hint, multiline, rows = 3, className, ref, ...props
}: InputFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const hasError = !!error

  const inputClasses = cn(
    'w-full rounded-md border bg-surface px-3 py-2 text-sm text-foreground',
    'placeholder:text-muted-foreground',
    'focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent',
    'disabled:opacity-60 disabled:cursor-not-allowed',
    hasError ? 'border-danger' : 'border-border',
    className,
  )

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
        {props.required && <span className="ml-0.5 text-danger">*</span>}
      </label>
      {multiline ? (
        <textarea
          id={id}
          ref={ref as React.Ref<HTMLTextAreaElement>}
          rows={rows}
          aria-invalid={hasError}
          aria-errormessage={hasError ? errorId : undefined}
          aria-describedby={hint ? hintId : undefined}
          className={cn(inputClasses, 'resize-y')}
          {...(props as React.ComponentProps<'textarea'>)}
        />
      ) : (
        <input
          id={id}
          ref={ref}
          aria-invalid={hasError}
          aria-errormessage={hasError ? errorId : undefined}
          aria-describedby={hint ? hintId : undefined}
          className={inputClasses}
          {...props}
        />
      )}
      {hint && !hasError && (
        <p id={hintId} className="text-xs text-muted-foreground">{hint}</p>
      )}
      {hasError && (
        <p id={errorId} role="alert" className="text-xs text-danger">{error}</p>
      )}
    </div>
  )
}
