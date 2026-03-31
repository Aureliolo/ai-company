import { cn } from '@/lib/utils'

interface ContentTypeMapping {
  label: string
  colorClass: string
}

function getContentTypeMapping(contentType: string): ContentTypeMapping {
  const lower = contentType.toLowerCase()
  if (lower === 'application/json') return { label: 'JSON', colorClass: 'text-accent border-accent/20 bg-accent/8' }
  if (lower === 'application/pdf') return { label: 'PDF', colorClass: 'text-warning border-warning/20 bg-warning/8' }
  if (lower.startsWith('image/')) return { label: 'Image', colorClass: 'text-success border-success/20 bg-success/8' }
  if (lower === 'text/markdown') return { label: 'Markdown', colorClass: 'text-text-secondary border-border bg-card' }
  if (lower === 'text/csv') return { label: 'CSV', colorClass: 'text-text-secondary border-border bg-card' }
  if (lower.startsWith('text/')) return { label: 'Text', colorClass: 'text-text-secondary border-border bg-card' }
  if (lower.startsWith('application/')) return { label: 'Binary', colorClass: 'text-text-muted border-border bg-card' }
  return { label: 'File', colorClass: 'text-text-muted border-border bg-card' }
}

export interface ContentTypeBadgeProps {
  contentType: string
  className?: string
}

export function ContentTypeBadge({ contentType, className }: ContentTypeBadgeProps) {
  const { label, colorClass } = getContentTypeMapping(contentType)

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-compact',
        colorClass,
        className,
      )}
    >
      {label}
    </span>
  )
}
