import { useEffect, useState } from 'react'
import { Package } from 'lucide-react'
import type { ConnectionType, McpCatalogEntry } from '@/api/types'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { useConnectionsData } from '@/hooks/useConnectionsData'
import { useMcpCatalogData } from '@/hooks/useMcpCatalogData'
import { useMcpCatalogStore } from '@/stores/mcp-catalog'
import { ConnectionFormModal } from './connections/ConnectionFormModal'
import { ConnectionsSkeleton } from './connections/ConnectionsSkeleton'
import { CatalogDetailDrawer } from './mcp-catalog/CatalogDetailDrawer'
import { CatalogGridView } from './mcp-catalog/CatalogGridView'
import { McpInstallWizard } from './mcp-catalog/McpInstallWizard'
import { McpCatalogSearch } from './mcp-catalog/McpCatalogSearch'

export default function McpCatalogPage() {
  const {
    visibleEntries,
    loading,
    searchLoading,
    searchQuery,
    hasSearch,
    error,
  } = useMcpCatalogData()
  // Keep connections warm so the install wizard can offer them.
  useConnectionsData()
  const installedEntryIds = useMcpCatalogStore((s) => s.installedEntryIds)
  const selectedEntry = useMcpCatalogStore((s) => s.selectedEntry)
  const selectEntry = useMcpCatalogStore((s) => s.selectEntry)
  const startInstall = useMcpCatalogStore((s) => s.startInstall)
  const uninstall = useMcpCatalogStore((s) => s.uninstall)
  const [createConnectionType, setCreateConnectionType] =
    useState<ConnectionType | null>(null)

  useEffect(() => {
    document.title = 'MCP Catalog · SynthOrg'
  }, [])

  const handleInstall = (entry: McpCatalogEntry) => {
    selectEntry(null)
    startInstall(entry.id)
  }

  const emptyTitle = hasSearch ? 'No matching entries' : 'Catalog empty'
  const emptyDescription = hasSearch
    ? `No catalog entries match "${searchQuery}".`
    : 'No MCP servers available in the bundled catalog.'

  return (
    <div className="flex flex-col gap-section-gap">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Package className="size-5 text-text-secondary" aria-hidden />
          <h1 className="text-lg font-semibold text-foreground">MCP Catalog</h1>
        </div>
        <McpCatalogSearch />
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md bg-danger/10 p-card text-sm text-danger"
        >
          {error}
        </div>
      )}

      {(loading || searchLoading) && visibleEntries.length === 0 ? (
        <ConnectionsSkeleton />
      ) : (
        <ErrorBoundary level="section">
          <CatalogGridView
            entries={visibleEntries}
            installedEntryIds={installedEntryIds}
            onSelect={selectEntry}
            onInstall={handleInstall}
            emptyTitle={emptyTitle}
            emptyDescription={emptyDescription}
          />
        </ErrorBoundary>
      )}

      <CatalogDetailDrawer
        entry={selectedEntry}
        installed={
          selectedEntry !== null && installedEntryIds.has(selectedEntry.id)
        }
        onClose={() => selectEntry(null)}
        onInstall={() => {
          if (selectedEntry) handleInstall(selectedEntry)
        }}
        onUninstall={() => {
          if (selectedEntry) void uninstall(selectedEntry.id)
        }}
      />

      <McpInstallWizard
        onRequestCreateConnection={(type) => setCreateConnectionType(type)}
      />

      <ConnectionFormModal
        open={createConnectionType !== null}
        mode="create"
        initialType={createConnectionType ?? undefined}
        onClose={() => setCreateConnectionType(null)}
      />
    </div>
  )
}
