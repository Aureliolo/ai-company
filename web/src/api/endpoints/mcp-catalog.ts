import { apiClient, unwrap, unwrapVoid } from '../client'
import type { ApiResponse } from '../types/http'
import type {
  McpCatalogEntry,
  McpInstallRequest,
  McpInstallResponse,
} from '../types/integrations'

export async function browseMcpCatalog(): Promise<readonly McpCatalogEntry[]> {
  const response = await apiClient.get<ApiResponse<readonly McpCatalogEntry[]>>(
    '/integrations/mcp/catalog',
  )
  return unwrap(response)
}

export async function searchMcpCatalog(
  query: string,
): Promise<readonly McpCatalogEntry[]> {
  const response = await apiClient.get<ApiResponse<readonly McpCatalogEntry[]>>(
    '/integrations/mcp/catalog/search',
    { params: { q: query } },
  )
  return unwrap(response)
}

export async function getMcpCatalogEntry(entryId: string): Promise<McpCatalogEntry> {
  const response = await apiClient.get<ApiResponse<McpCatalogEntry>>(
    `/integrations/mcp/catalog/${encodeURIComponent(entryId)}`,
  )
  return unwrap(response)
}

export async function installMcpServer(
  data: McpInstallRequest,
): Promise<McpInstallResponse> {
  const response = await apiClient.post<ApiResponse<McpInstallResponse>>(
    '/integrations/mcp/catalog/install',
    data,
  )
  return unwrap(response)
}

export async function uninstallMcpServer(entryId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/integrations/mcp/catalog/install/${encodeURIComponent(entryId)}`,
  )
  unwrapVoid(response)
}
