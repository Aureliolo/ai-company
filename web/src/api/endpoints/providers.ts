import { apiClient, unwrap, unwrapVoid } from '../client'
import type {
  AddAllowlistEntryRequest,
  ApiResponse,
  CreateFromPresetRequest,
  CreateProviderRequest,
  DiscoverModelsResponse,
  DiscoveryPolicyResponse,
  LocalModelParams,
  ProbePresetResponse,
  ProviderConfig,
  ProviderHealthSummary,
  ProviderModelResponse,
  ProviderPreset,
  PullProgressEvent,
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

export async function getProviderModels(name: string): Promise<ProviderModelResponse[]> {
  const response = await apiClient.get<ApiResponse<ProviderModelResponse[]>>(`/providers/${encodeURIComponent(name)}/models`)
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
  // Extended timeout: local providers (Ollama) may need to load models into memory
  const response = await apiClient.post<ApiResponse<TestConnectionResponse>>(
    `/providers/${encodeURIComponent(name)}/test`,
    data ?? {},
    { timeout: 120_000 },
  )
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

/**
 * Pull a model on a local provider via SSE streaming.
 *
 * Uses fetch + ReadableStream because the endpoint is POST-based
 * and EventSource only supports GET.
 */
export async function pullModel(
  name: string,
  modelName: string,
  onProgress: (event: PullProgressEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const baseUrl = apiClient.defaults.baseURL ?? ''
  const url = `${baseUrl}/providers/${encodeURIComponent(name)}/models/pull`
  const token = localStorage.getItem('auth_token')

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ model_name: modelName }),
    signal,
  })

  if (!response.ok || !response.body) {
    throw new Error(`Pull failed: HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6)) as PullProgressEvent
          onProgress(event)
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }
}

export async function deleteModel(name: string, modelId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/providers/${encodeURIComponent(name)}/models/${encodeURIComponent(modelId)}`,
  )
  unwrapVoid(response)
}

export async function updateModelConfig(
  name: string,
  modelId: string,
  params: LocalModelParams,
): Promise<ProviderModelResponse> {
  const response = await apiClient.put<ApiResponse<ProviderModelResponse>>(
    `/providers/${encodeURIComponent(name)}/models/${encodeURIComponent(modelId)}/config`,
    { local_params: params },
  )
  return unwrap(response)
}
