import { apiClient, unwrap } from '../client'
import type { ApiResponse, SettingDefinition, SettingEntry, UpdateSettingRequest } from '../types'

export async function getSchema(): Promise<SettingDefinition[]> {
  const response = await apiClient.get<ApiResponse<SettingDefinition[]>>('/settings/_schema')
  return unwrap(response)
}

export async function getNamespaceSchema(namespace: string): Promise<SettingDefinition[]> {
  const response = await apiClient.get<ApiResponse<SettingDefinition[]>>(
    `/settings/_schema/${encodeURIComponent(namespace)}`,
  )
  return unwrap(response)
}

export async function getAllSettings(): Promise<SettingEntry[]> {
  const response = await apiClient.get<ApiResponse<SettingEntry[]>>('/settings')
  return unwrap(response)
}

export async function getNamespaceSettings(namespace: string): Promise<SettingEntry[]> {
  const response = await apiClient.get<ApiResponse<SettingEntry[]>>(
    `/settings/${encodeURIComponent(namespace)}`,
  )
  return unwrap(response)
}

export async function updateSetting(
  namespace: string,
  key: string,
  data: UpdateSettingRequest,
): Promise<SettingEntry> {
  const response = await apiClient.put<ApiResponse<SettingEntry>>(
    `/settings/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
    data,
  )
  return unwrap(response)
}

export async function resetSetting(namespace: string, key: string): Promise<void> {
  await apiClient.delete(
    `/settings/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
  )
}
