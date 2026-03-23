import { useState, useEffect } from "react"
import { useTheme } from "@/themes/provider.tsx"
import { NavItem } from "./nav-item.tsx"
import { useNavItems, SidebarHeader, SidebarSearch } from "./shared.tsx"
import { MenuIcon } from "@/components/nav-icons.tsx"

/** Stealth: Hidden sidebar (hamburger toggle, content takes full width by default) */
export function SidebarHidden() {
  const theme = useTheme()
  const navItems = useNavItems()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) setOpen(false)
    }
    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [open])

  return (
    <>
      {/* Hamburger toggle - always visible */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed top-2 left-3 z-50 p-2 rounded bg-bg-surface border border-border text-text-muted hover:text-text-primary hover:bg-bg-card transition-colors"
          aria-label="Open navigation"
        >
          <MenuIcon size={16} />
        </button>
      )}

      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Drawer */}
      {open && (
        <aside
          className="fixed top-0 left-0 h-full z-50 bg-bg-surface border-r border-border flex flex-col overflow-hidden"
          style={{ width: theme.chrome.sidebarWidth }}
        >
          <div className="flex items-center justify-between">
            <SidebarHeader />
            <button
              onClick={() => setOpen(false)}
              className="p-2 mr-2 rounded text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
              aria-label="Close navigation"
            >
              x
            </button>
          </div>
          <nav className="flex-1 overflow-y-auto py-2">
            {navItems.map((item) => (
              <NavItem key={item.label} {...item} />
            ))}
          </nav>
          <SidebarSearch />
        </aside>
      )}
    </>
  )
}
