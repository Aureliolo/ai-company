import { apiClient, unwrap, unwrapVoid } from '../client'
import type { ApiResponse, BackupInfo, BackupManifest, RestoreRequest, RestoreResponse } from '../types'

export async function createBackup(): Promise<BackupManifest> {
  const response = await apiClient.post<ApiResponse<BackupManifest>>('/admin/backups')
  return unwrap(response)
}

export async function listBackups(): Promise<BackupInfo[]> {
  const response = await apiClient.get<ApiResponse<BackupInfo[]>>('/admin/backups')
  return unwrap(response)
}

export async function getBackup(backupId: string): Promise<BackupManifest> {
  const response = await apiClient.get<ApiResponse<BackupManifest>>(`/admin/backups/${encodeURIComponent(backupId)}`)
  return unwrap(response)
}

export async function deleteBackup(backupId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(`/admin/backups/${encodeURIComponent(backupId)}`)
  unwrapVoid(response)
}

export async function restoreBackup(data: RestoreRequest): Promise<RestoreResponse> {
  const response = await apiClient.post<ApiResponse<RestoreResponse>>('/admin/backups/restore', data)
  return unwrap(response)
}
