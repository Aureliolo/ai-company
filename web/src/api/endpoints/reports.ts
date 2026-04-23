import { apiClient, unwrap } from '../client'
import type { components } from '../types/generated'
import type { ApiResponse } from '../types/http'

type Schemas = components['schemas']

export type ReportPeriod = Schemas['ReportPeriod']
export type ReportResponse = Schemas['ReportResponse']
export type GenerateReportRequest = Schemas['GenerateReportRequest']

export interface ListReportPeriodsOptions {
  signal?: AbortSignal
}

export async function listReportPeriods(
  options: ListReportPeriodsOptions = {},
): Promise<ReportPeriod[]> {
  const response = await apiClient.get<ApiResponse<ReportPeriod[]>>(
    '/reports/periods',
    { signal: options.signal },
  )
  return unwrap(response)
}

export async function generateReport(
  period: ReportPeriod,
): Promise<ReportResponse> {
  const response = await apiClient.post<ApiResponse<ReportResponse>>(
    '/reports/generate',
    { period } satisfies GenerateReportRequest,
  )
  return unwrap(response)
}
