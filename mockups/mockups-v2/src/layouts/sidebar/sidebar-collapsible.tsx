import { useState } from "react"
import { motion } from "framer-motion"
import { useTheme } from "@/themes/provider.tsx"
import { NavItem } from "./nav-item.tsx"
import { useNavItems, SidebarHeader, SidebarSearch } from "./shared.tsx"
import { MenuIcon } from "@/components/nav-icons.tsx"

/** Warm Ops: Collapsible sidebar (expanded by default, can collapse to icon rail) */
export function SidebarCollapsible() {
  const theme = useTheme()
  const navItems = useNavItems()
  const [collapsed, setCollapsed] = useState(false)

  const width = collapsed
    ? theme.chrome.sidebarCollapsedWidth
    : theme.chrome.sidebarWidth

  return (
    <motion.aside
      className="shrink-0 bg-bg-surface border-r border-border flex flex-col h-full overflow-hidden"
      animate={{ width }}
      transition={
        theme.animation.springConfig
          ? { type: "spring", ...theme.animation.springConfig }
          : { duration: 0.2 }
      }
    >
      <div className="flex items-center justify-between px-2 pt-2">
        {!collapsed && <SidebarHeader />}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <MenuIcon size={14} />
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto py-2">
        {navItems.map((item) => (
          <NavItem key={item.label} {...item} compact={collapsed} />
        ))}
      </nav>
      {!collapsed && <SidebarSearch />}
    </motion.aside>
  )
}
