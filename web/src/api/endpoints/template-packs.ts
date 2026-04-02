import { apiClient, unwrap } from '../client'
import type {
  ApiResponse,
  ApplyTemplatePackRequest,
  ApplyTemplatePackResponse,
  PackInfoResponse,
} from '../types'

export async function listTemplatePacks(): Promise<readonly PackInfoResponse[]> {
  const response = await apiClient.get<ApiResponse<readonly PackInfoResponse[]>>(
    '/template-packs',
  )
  return unwrap(response)
}

export async function applyTemplatePack(
  data: ApplyTemplatePackRequest,
): Promise<ApplyTemplatePackResponse> {
  const response = await apiClient.post<ApiResponse<ApplyTemplatePackResponse>>(
    '/template-packs/apply',
    data,
  )
  return unwrap(response)
}
