import { http, HttpResponse } from 'msw'
import type { getHealth } from '@/api/endpoints/health'
import { successFor } from './helpers'

export const healthHandlers = [
  http.get('/api/v1/readyz', () =>
    HttpResponse.json(
      successFor<typeof getHealth>({
        status: 'ok',
        persistence: true,
        message_bus: true,
        telemetry: 'disabled',
        version: '0.6.4',
        uptime_seconds: 0,
      }),
    ),
  ),
]
