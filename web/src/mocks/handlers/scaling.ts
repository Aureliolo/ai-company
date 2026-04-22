import { http, HttpResponse } from 'msw'
import type {
  ScalingDecisionResponse,
  getScalingSignals,
  getScalingStrategies,
  triggerScalingEvaluation,
} from '@/api/endpoints/scaling'
import type { PaginatedResponse } from '@/api/types/http'
import { successFor } from './helpers'

export const scalingHandlers = [
  http.get('/api/v1/scaling/strategies', () =>
    HttpResponse.json(successFor<typeof getScalingStrategies>([])),
  ),
  http.get('/api/v1/scaling/decisions', () => {
    // getScalingDecisions() collapses the paginated response to { data, total }
    // so paginatedFor<typeof endpoint> cannot be used here. Construct the
    // wire envelope directly, annotated for compile-time safety.
    const body: PaginatedResponse<ScalingDecisionResponse> = {
      data: [],
      error: null,
      error_detail: null,
      success: true,
      pagination: {
        total: 0,
        offset: 0,
        limit: 50,
        next_cursor: null,
        has_more: false,
      },
    }
    return HttpResponse.json(body)
  }),
  http.get('/api/v1/scaling/signals', () =>
    HttpResponse.json(successFor<typeof getScalingSignals>([])),
  ),
  http.post('/api/v1/scaling/evaluate', () =>
    HttpResponse.json(successFor<typeof triggerScalingEvaluation>([])),
  ),
]
