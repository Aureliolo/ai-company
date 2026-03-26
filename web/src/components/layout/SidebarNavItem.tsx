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
}

export function SidebarNavItem({
  to,
  icon: Icon,
  label,
  collapsed,
  badge,
  dotColor,
  end,
}: SidebarNavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
          'text-text-secondary hover:bg-card-hover hover:text-foreground',
          isActive && 'bg-card text-accent',
          collapsed && 'justify-center px-0',
        )
      }
    >
      <Icon className="size-5 shrink-0" aria-hidden="true" />
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{label}</span>
          {badge !== undefined && badge > 0 && (
            <span
              className={cn(
                'flex size-5 items-center justify-center',
                'rounded-full bg-danger',
                'text-xs font-semibold text-foreground',
              )}
            >
              {badge > 99 ? '99+' : badge}
            </span>
          )}
          {dotColor && (
            <span
              className={cn('size-2 rounded-full', dotColor)}
              aria-hidden="true"
            />
          )}
        </>
      )}
    </NavLink>
  )
}
