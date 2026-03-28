import { useCallback, useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const DEBOUNCE_MS = 200

export interface SearchInputProps {
  value: string
  onChange: (query: string) => void
  className?: string
}

export function SearchInput({ value, onChange, className }: SearchInputProps) {
  const [local, setLocal] = useState(value)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync external value changes (e.g. clearing from parent)
  const prevValueRef = useRef(value)
  if (value !== prevValueRef.current) {
    prevValueRef.current = value
    setLocal(value)
  }

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = e.target.value
      setLocal(next)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => onChange(next), DEBOUNCE_MS)
    },
    [onChange],
  )

  const handleClear = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    setLocal('')
    onChange('')
  }, [onChange])

  return (
    <div className={cn('relative', className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted" aria-hidden />
      <input
        type="text"
        value={local}
        onChange={handleChange}
        placeholder="Search settings..."
        className="h-9 w-full rounded-md border border-border bg-surface pl-9 pr-8 text-sm text-foreground outline-none placeholder:text-text-muted focus:border-accent focus:ring-1 focus:ring-accent"
        aria-label="Search settings"
      />
      {local && (
        <button
          type="button"
          onClick={handleClear}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-text-muted transition-colors hover:text-foreground"
          aria-label="Clear search"
        >
          <X className="size-3.5" />
        </button>
      )}
    </div>
  )
}
