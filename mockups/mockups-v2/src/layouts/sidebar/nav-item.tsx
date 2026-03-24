import { Link, useLocation, useParams } from "react-router-dom"
import type { ReactNode } from "react"

interface NavItemProps {
  label: string
  href: string
  icon: ReactNode
  badge?: number
  compact?: boolean
}

export function NavItem({ label, href, icon, badge, compact }: NavItemProps) {
  const location = useLocation()
  const { variation } = useParams()
  const fullHref = href === "#" ? "#" : `/${variation}${href}`

  const isActive =
    href !== "#" &&
    (href === "/dashboard"
      ? location.pathname.endsWith("/dashboard")
      : location.pathname.includes(href))

  return (
    <Link
      to={fullHref}
      className={`
        flex items-center gap-2.5 px-4 py-2 text-[13px] no-underline relative
        transition-colors duration-200
        border-l-2
        ${
          isActive
            ? "bg-accent/[0.06] text-accent border-l-accent font-medium"
            : "text-text-secondary border-l-transparent hover:bg-white/[0.04] hover:text-text-primary"
        }
        ${compact ? "px-0 justify-center" : ""}
      `}
    >
      <span className={isActive ? "text-accent" : "text-text-muted"}>
        {icon}
      </span>
      {!compact && (
        <>
          <span className="flex-1">{label}</span>
          {badge != null && badge > 0 && (
            <span className="bg-warning/15 border border-warning/30 text-warning text-[10px] font-mono font-semibold px-1.5 py-px rounded leading-snug">
              {badge}
            </span>
          )}
        </>
      )}
    </Link>
  )
}
