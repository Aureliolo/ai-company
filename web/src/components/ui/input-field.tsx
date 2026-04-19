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
  /**
   * Decorative leading icon rendered inside the input. Positioned relative to
   * the input box (not the label), so it stays vertically centered on the
   * input. Receives `pointer-events-none` automatically.
   */
  leadingIcon?: React.ReactNode
  /**
   * Trailing element rendered inside the input (e.g. a clear button).
   * Unlike `leadingIcon`, pointer events pass through -- consumers are
   * responsible for interactivity.
   */
  trailingElement?: React.ReactNode
}

interface TextareaProps extends BaseFieldProps, Omit<React.ComponentProps<'textarea'>, 'id'> {
  multiline: true
  ref?: React.Ref<HTMLTextAreaElement>
}

export type InputFieldProps = InputProps | TextareaProps

export function InputField(props: InputFieldProps) {
  const {
    label, error, hint, multiline, className, ref, onValueChange, onChange,
    ...rest
  } = props
  const leadingIcon = !multiline ? (props as InputProps).leadingIcon : undefined
  const trailingElement = !multiline
    ? (props as InputProps).trailingElement
    : undefined
  // Strip icon props from the spread so they don't leak onto the DOM element.
  const domProps = rest as Record<string, unknown>
  delete domProps.leadingIcon
  delete domProps.trailingElement
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
    leadingIcon ? 'pl-8' : undefined,
    trailingElement ? 'pr-8' : undefined,
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
          {...(domProps as Omit<React.ComponentProps<'textarea'>, 'onChange'>)}
        />
      ) : (
        <div className="relative">
          {leadingIcon && (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute left-2.5 top-1/2 flex -translate-y-1/2 items-center text-muted-foreground"
            >
              {leadingIcon}
            </span>
          )}
          <input
            id={id}
            ref={ref as React.Ref<HTMLInputElement>}
            aria-invalid={hasError}
            aria-errormessage={hasError ? errorId : undefined}
            aria-describedby={hint && !hasError ? hintId : undefined}
            className={inputClasses}
            onChange={handleInputChange}
            {...(domProps as Omit<React.ComponentProps<'input'>, 'onChange'>)}
          />
          {trailingElement && (
            <span className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center">
              {trailingElement}
            </span>
          )}
        </div>
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
