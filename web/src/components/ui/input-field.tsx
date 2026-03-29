import { useId } from 'react'
import { cn } from '@/lib/utils'

interface BaseFieldProps {
  label: string
  error?: string | null
  hint?: string
  /** Convenience callback that receives the value string directly. */
  onValueChange?: (value: string) => void
}

interface InputProps extends BaseFieldProps, Omit<React.ComponentProps<'input'>, 'id'> {
  multiline?: false
  ref?: React.Ref<HTMLInputElement>
}

interface TextareaProps extends BaseFieldProps, Omit<React.ComponentProps<'textarea'>, 'id'> {
  multiline: true
  ref?: React.Ref<HTMLTextAreaElement>
}

export type InputFieldProps = InputProps | TextareaProps

export function InputField({
  label, error, hint, multiline, className, ref, onValueChange, onChange, ...props
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

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onValueChange?.(e.target.value)
    ;(onChange as React.ChangeEventHandler<HTMLInputElement> | undefined)?.(e)
  }

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onValueChange?.(e.target.value)
    ;(onChange as React.ChangeEventHandler<HTMLTextAreaElement> | undefined)?.(e)
  }

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
          aria-invalid={hasError}
          aria-errormessage={hasError ? errorId : undefined}
          aria-describedby={hint && !hasError ? hintId : undefined}
          className={cn(inputClasses, 'resize-y')}
          onChange={handleTextareaChange}
          {...(props as Omit<React.ComponentProps<'textarea'>, 'onChange'>)}
        />
      ) : (
        <input
          id={id}
          ref={ref as React.Ref<HTMLInputElement>}
          aria-invalid={hasError}
          aria-errormessage={hasError ? errorId : undefined}
          aria-describedby={hint && !hasError ? hintId : undefined}
          className={inputClasses}
          onChange={handleInputChange}
          {...(props as Omit<React.ComponentProps<'input'>, 'onChange'>)}
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
