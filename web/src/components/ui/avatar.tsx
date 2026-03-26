import { cn } from '@/lib/utils'

const SIZE_CLASSES = {
  sm: 'size-6 text-[10px]',
  md: 'size-8 text-xs',
  lg: 'size-10 text-sm',
} as const

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return ''
  const first = parts[0]!
  if (parts.length === 1) return first[0]!.toUpperCase()
  const last = parts[parts.length - 1]!
  return (first[0]! + last[0]!).toUpperCase()
}

interface AvatarProps {
  name: string
  size?: 'sm' | 'md' | 'lg'
  borderColor?: string
  className?: string
}

export function Avatar({ name, size = 'md', borderColor, className }: AvatarProps) {
  const initials = getInitials(name)

  return (
    <span
      role="img"
      aria-label={name || undefined}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full',
        'bg-accent-dim font-mono font-semibold text-foreground',
        borderColor && 'border-2',
        borderColor,
        SIZE_CLASSES[size],
        className,
      )}
    >
      {initials}
    </span>
  )
}
