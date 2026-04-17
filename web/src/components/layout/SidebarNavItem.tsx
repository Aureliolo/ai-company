import type { LucideIcon } from 'lucide-react'
import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'

interface SidebarNavItemProps {
  to: string
  icon: LucideIcon
  label: string
  collapsed: boolean
  badge?: number
  dotColor?: string
  end?: boolean
  /** Render as a plain `<a href>` instead of a React Router NavLink. */
  external?: boolean
}

export function SidebarNavItem({
  to,
  icon: Icon,
  label,
  collapsed,
  badge,
  dotColor,
  end,
  external,
}: SidebarNavItemProps) {
  const baseClass = cn(
    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
    'text-text-secondary hover:bg-card-hover hover:text-foreground',
    collapsed && 'justify-center px-0',
  )

  const content = (
    <>
      <Icon className="size-5 shrink-0" aria-hidden="true" />
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{label}</span>
          <span aria-live="polite" className="contents">
            {badge !== undefined && badge > 0 && (
              <span
                aria-label={`${badge} pending ${label.toLowerCase()}`}
                className={cn(
                  'flex size-5 items-center justify-center',
                  'rounded-full bg-danger',
                  'text-xs font-semibold text-white',
                )}
              >
                {badge > 99 ? '99+' : badge}
              </span>
            )}
          </span>
          {dotColor && (
            <span
              className={cn('size-2 rounded-full', dotColor)}
              aria-hidden="true"
            />
          )}
        </>
      )}
    </>
  )

  if (external) {
    // When collapsed the visible label is hidden, so the sr-only span
    // has to carry both the destination name and the new-tab hint.
    // Expanded renders the label visibly, so only the hint is needed.
    const srText = collapsed ? `${label} (opens in new tab)` : '(opens in new tab)'
    return (
      <a
        href={to}
        title={collapsed ? label : undefined}
        className={baseClass}
        target="_blank"
        rel="noopener noreferrer"
      >
        {content}
        <span className="sr-only">{srText}</span>
      </a>
    )
  }

  return (
    <NavLink
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(baseClass, isActive && 'bg-card text-accent')
      }
    >
      {content}
    </NavLink>
  )
}
