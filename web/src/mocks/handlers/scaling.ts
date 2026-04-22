import { http, HttpResponse } from 'msw'
import type {
  ScalingDecisionResponse,
  getScalingDecisions,
  getScalingSignals,
  getScalingStrategies,
  triggerScalingEvaluation,
} from '@/api/endpoints/scaling'
import { emptyPage, paginatedFor, successFor } from './helpers'

export const scalingHandlers = [
  http.get('/api/v1/scaling/strategies', () =>
    HttpResponse.json(successFor<typeof getScalingStrategies>([])),
  ),
  http.get('/api/v1/scaling/decisions', () =>
    HttpResponse.json(
      paginatedFor<typeof getScalingDecisions>(
        emptyPage<ScalingDecisionResponse>(50),
      ),
    ),
  ),
  http.get('/api/v1/scaling/signals', () =>
    HttpResponse.json(successFor<typeof getScalingSignals>([])),
  ),
  http.post('/api/v1/scaling/evaluate', () =>
    HttpResponse.json(successFor<typeof triggerScalingEvaluation>([])),
  ),
]
