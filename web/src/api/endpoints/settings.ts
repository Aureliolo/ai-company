import { apiClient, unwrap, unwrapVoid } from '../client'
import type { ApiResponse, SettingDefinition, SettingEntry, SettingNamespace, UpdateSettingRequest } from '../types'

export async function getSchema(): Promise<SettingDefinition[]> {
  const response = await apiClient.get<ApiResponse<SettingDefinition[]>>('/settings/_schema')
  return unwrap(response)
}

export async function getNamespaceSchema(namespace: SettingNamespace): Promise<SettingDefinition[]> {
  const response = await apiClient.get<ApiResponse<SettingDefinition[]>>(
    `/settings/_schema/${encodeURIComponent(namespace)}`,
  )
  return unwrap(response)
}

export async function getAllSettings(): Promise<SettingEntry[]> {
  const response = await apiClient.get<ApiResponse<SettingEntry[]>>('/settings')
  return unwrap(response)
}

export async function getNamespaceSettings(namespace: SettingNamespace): Promise<SettingEntry[]> {
  const response = await apiClient.get<ApiResponse<SettingEntry[]>>(
    `/settings/${encodeURIComponent(namespace)}`,
  )
  return unwrap(response)
}

export async function updateSetting(
  namespace: SettingNamespace,
  key: string,
  data: UpdateSettingRequest,
): Promise<SettingEntry> {
  const response = await apiClient.put<ApiResponse<SettingEntry>>(
    `/settings/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
    data,
  )
  return unwrap(response)
}

export async function resetSetting(namespace: SettingNamespace, key: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/settings/${encodeURIComponent(namespace)}/${encodeURIComponent(key)}`,
  )
  unwrapVoid(response)
}
