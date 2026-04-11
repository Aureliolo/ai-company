import { Search, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useMcpCatalogStore } from '@/stores/mcp-catalog'

export function McpCatalogSearch() {
  const searchQuery = useMcpCatalogStore((s) => s.searchQuery)
  const setSearchQuery = useMcpCatalogStore((s) => s.setSearchQuery)

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-md border border-border bg-surface',
        'px-3 py-2 text-sm',
      )}
    >
      <Search className="size-4 text-text-muted" aria-hidden />
      <input
        type="search"
        value={searchQuery}
        onChange={(event) => void setSearchQuery(event.target.value)}
        placeholder="Search MCP catalog..."
        aria-label="Search MCP catalog"
        className="min-w-48 bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none"
      />
      {searchQuery && (
        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label="Clear search"
          onClick={() => void setSearchQuery('')}
        >
          <X className="size-4" aria-hidden />
        </Button>
      )}
    </div>
  )
}
