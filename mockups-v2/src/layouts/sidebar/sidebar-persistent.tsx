import { useTheme } from "@/themes/provider.tsx"
import { NavItem } from "./nav-item.tsx"
import { useNavItems, SidebarHeader, SidebarSearch } from "./shared.tsx"

/** Signal: Persistent sidebar with notification badges */
export function SidebarPersistent() {
  const theme = useTheme()
  const navItems = useNavItems()

  // Add notification badges to more items for Signal variation
  const enhancedItems = navItems.map((item) => {
    if (item.label === "Messages") return { ...item, badge: 7 }
    if (item.label === "Tasks") return { ...item, badge: 12 }
    return item
  })

  return (
    <aside
      className="shrink-0 bg-bg-surface border-r border-border flex flex-col h-full overflow-hidden"
      style={{ width: theme.chrome.sidebarWidth }}
    >
      <SidebarHeader />
      <nav className="flex-1 overflow-y-auto py-2">
        {enhancedItems.map((item) => (
          <NavItem key={item.label} {...item} />
        ))}
      </nav>
      <SidebarSearch />
    </aside>
  )
}
