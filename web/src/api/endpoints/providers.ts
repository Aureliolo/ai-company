import { apiClient, unwrap, unwrapVoid } from '../client'
import type {
  AddAllowlistEntryRequest,
  ApiResponse,
  CreateFromPresetRequest,
  CreateProviderRequest,
  DiscoverModelsResponse,
  DiscoveryPolicyResponse,
  ProbePresetResponse,
  ProviderConfig,
  ProviderHealthSummary,
  ProviderModelConfig,
  ProviderPreset,
  RemoveAllowlistEntryRequest,
  TestConnectionRequest,
  TestConnectionResponse,
  UpdateProviderRequest,
} from '../types'

export async function listProviders(): Promise<Record<string, ProviderConfig>> {
  const response = await apiClient.get<ApiResponse<Record<string, ProviderConfig>>>('/providers')
  const raw = unwrap<Record<string, ProviderConfig>>(response)
  const result: Record<string, ProviderConfig> = Object.create(null) as Record<string, ProviderConfig>
  for (const [key, provider] of Object.entries(raw)) {
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') continue
    result[key] = provider
  }
  return result
}

export async function getProvider(name: string): Promise<ProviderConfig> {
  const response = await apiClient.get<ApiResponse<ProviderConfig>>(`/providers/${encodeURIComponent(name)}`)
  return unwrap(response)
}

export async function getProviderModels(name: string): Promise<ProviderModelConfig[]> {
  const response = await apiClient.get<ApiResponse<ProviderModelConfig[]>>(`/providers/${encodeURIComponent(name)}/models`)
  return unwrap(response)
}

export async function getProviderHealth(name: string): Promise<ProviderHealthSummary> {
  const response = await apiClient.get<ApiResponse<ProviderHealthSummary>>(`/providers/${encodeURIComponent(name)}/health`)
  return unwrap(response)
}

export async function createProvider(data: CreateProviderRequest): Promise<ProviderConfig> {
  const response = await apiClient.post<ApiResponse<ProviderConfig>>('/providers', data)
  return unwrap(response)
}

export async function updateProvider(name: string, data: UpdateProviderRequest): Promise<ProviderConfig> {
  const response = await apiClient.put<ApiResponse<ProviderConfig>>(`/providers/${encodeURIComponent(name)}`, data)
  return unwrap(response)
}

export async function deleteProvider(name: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(`/providers/${encodeURIComponent(name)}`)
  unwrapVoid(response)
}

export async function testConnection(name: string, data?: TestConnectionRequest): Promise<TestConnectionResponse> {
  const response = await apiClient.post<ApiResponse<TestConnectionResponse>>(`/providers/${encodeURIComponent(name)}/test`, data ?? {})
  return unwrap(response)
}

export async function listPresets(): Promise<ProviderPreset[]> {
  const response = await apiClient.get<ApiResponse<ProviderPreset[]>>('/providers/presets')
  return unwrap(response)
}

export async function createFromPreset(data: CreateFromPresetRequest): Promise<ProviderConfig> {
  const response = await apiClient.post<ApiResponse<ProviderConfig>>('/providers/from-preset', data)
  return unwrap(response)
}

export async function probePreset(presetName: string): Promise<ProbePresetResponse> {
  const response = await apiClient.post<ApiResponse<ProbePresetResponse>>('/providers/probe-preset', {
    preset_name: presetName,
  })
  return unwrap(response)
}

export async function discoverModels(
  name: string,
  presetHint?: string,
): Promise<DiscoverModelsResponse> {
  const params = presetHint ? { preset_hint: presetHint } : undefined
  const response = await apiClient.post<ApiResponse<DiscoverModelsResponse>>(
    `/providers/${encodeURIComponent(name)}/discover-models`,
    undefined,
    { params },
  )
  return unwrap(response)
}

export async function getDiscoveryPolicy(): Promise<DiscoveryPolicyResponse> {
  const response = await apiClient.get<ApiResponse<DiscoveryPolicyResponse>>('/providers/discovery-policy')
  return unwrap(response)
}

export async function addAllowlistEntry(data: AddAllowlistEntryRequest): Promise<DiscoveryPolicyResponse> {
  const response = await apiClient.post<ApiResponse<DiscoveryPolicyResponse>>('/providers/discovery-policy/entries', data)
  return unwrap(response)
}

export async function removeAllowlistEntry(data: RemoveAllowlistEntryRequest): Promise<DiscoveryPolicyResponse> {
  const response = await apiClient.post<ApiResponse<DiscoveryPolicyResponse>>('/providers/discovery-policy/remove-entry', data)
  return unwrap(response)
}
