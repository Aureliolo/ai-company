import { http, HttpResponse } from 'msw'
import type {
  getMetaConfig,
  getSignals,
  listABTests,
  listProposals,
  postChat,
} from '@/api/endpoints/meta'
import { apiError, successFor } from './helpers'

export const metaHandlers = [
  http.get('/api/v1/meta/config', () =>
    HttpResponse.json(
      successFor<typeof getMetaConfig>({
        enabled: false,
        chief_of_staff_enabled: false,
        config_tuning_enabled: false,
        architecture_proposals_enabled: false,
        prompt_tuning_enabled: false,
        code_modification_enabled: false,
      }),
    ),
  ),
  http.get('/api/v1/meta/proposals', () =>
    HttpResponse.json(successFor<typeof listProposals>([])),
  ),
  http.get('/api/v1/meta/signals', () =>
    HttpResponse.json(
      successFor<typeof getSignals>({ enabled: false, domains: [] }),
    ),
  ),
  http.get('/api/v1/meta/ab-tests', () =>
    HttpResponse.json(successFor<typeof listABTests>([])),
  ),
  http.post('/api/v1/meta/chat', async ({ request }) => {
    const body = (await request.json()) as { question?: string }
    if (!body.question || !body.question.trim()) {
      return HttpResponse.json(apiError('Question must not be blank'), {
        status: 400,
      })
    }
    return HttpResponse.json(
      successFor<typeof postChat>({
        answer: 'default response',
        sources: [],
        confidence: 0,
      }),
    )
  }),
]
