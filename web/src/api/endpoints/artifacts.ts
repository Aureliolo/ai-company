import { apiClient, unwrap, unwrapPaginated, unwrapVoid, type PaginatedResult } from '../client'
import type { Artifact, ArtifactFilters, CreateArtifactRequest } from '../types/artifacts'
import type { ApiResponse, PaginatedResponse } from '../types/http'

export async function listArtifacts(filters?: ArtifactFilters): Promise<PaginatedResult<Artifact>> {
  const response = await apiClient.get<PaginatedResponse<Artifact>>('/artifacts', { params: filters })
  return unwrapPaginated<Artifact>(response)
}

export async function getArtifact(artifactId: string): Promise<Artifact> {
  const response = await apiClient.get<ApiResponse<Artifact>>(`/artifacts/${encodeURIComponent(artifactId)}`)
  return unwrap(response)
}

export async function createArtifact(data: CreateArtifactRequest): Promise<Artifact> {
  const response = await apiClient.post<ApiResponse<Artifact>>('/artifacts', data)
  return unwrap(response)
}

export async function deleteArtifact(artifactId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(`/artifacts/${encodeURIComponent(artifactId)}`)
  unwrapVoid(response)
}

export async function downloadArtifactContent(artifactId: string): Promise<Blob> {
  const response = await apiClient.get<Blob>(
    `/artifacts/${encodeURIComponent(artifactId)}/content`,
    { responseType: 'blob' },
  )
  return response.data
}

export async function getArtifactContentText(artifactId: string): Promise<string> {
  const response = await apiClient.get<string>(
    `/artifacts/${encodeURIComponent(artifactId)}/content`,
    { responseType: 'text' },
  )
  return response.data
}
