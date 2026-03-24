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
          'text-surface-500 hover:bg-surface-100 hover:text-surface-700',
          isActive && 'bg-surface-100 text-brand-400',
          collapsed && 'justify-center px-0',
        )
      }
    >
      <Icon className="size-5 shrink-0" aria-hidden="true" />
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{label}</span>
          {badge !== undefined && badge > 0 && (
            <span className="flex size-5 items-center justify-center rounded-full bg-danger-500 text-xs font-semibold text-white">
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
