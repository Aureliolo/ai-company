import { apiClient, unwrap } from '../client'
import type { ForecastResponse, OverviewMetrics, TrendMetric, TrendPeriod, TrendsResponse } from '../types/analytics'
import type { ApiResponse } from '../types/http'

export async function getOverviewMetrics(): Promise<OverviewMetrics> {
  const response = await apiClient.get<ApiResponse<OverviewMetrics>>('/analytics/overview')
  return unwrap(response)
}

export async function getTrends(
  period?: TrendPeriod,
  metric?: TrendMetric,
): Promise<TrendsResponse> {
  const response = await apiClient.get<ApiResponse<TrendsResponse>>('/analytics/trends', {
    params: period !== undefined || metric !== undefined ? { period, metric } : undefined,
  })
  return unwrap(response)
}

export async function getForecast(horizonDays?: number): Promise<ForecastResponse> {
  const response = await apiClient.get<ApiResponse<ForecastResponse>>('/analytics/forecast', {
    params: horizonDays !== undefined ? { horizon_days: horizonDays } : undefined,
  })
  return unwrap(response)
}
