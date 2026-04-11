import {
  Brain,
  Database,
  Folder,
  GitBranch,
  Globe,
  MessageSquare,
  type LucideIcon,
  Package,
  Search,
} from 'lucide-react'

/**
 * Map bundled MCP catalog entry ids to lucide-react icons.
 *
 * Unknown ids fall back to a generic ``Package`` icon so new catalog
 * entries render without crashing until an icon is added here.
 */
const ENTRY_ICONS: Record<string, LucideIcon> = {
  'github-mcp': GitBranch,
  'slack-mcp': MessageSquare,
  'filesystem-mcp': Folder,
  'postgres-mcp': Database,
  'sqlite-mcp': Database,
  'brave-search-mcp': Search,
  'puppeteer-mcp': Globe,
  'memory-mcp': Brain,
}

export function getCatalogEntryIcon(entryId: string): LucideIcon {
  return ENTRY_ICONS[entryId] ?? Package
}
