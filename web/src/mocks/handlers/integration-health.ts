import { http, HttpResponse } from 'msw'
import type {
  getSingleIntegrationHealth,
  listIntegrationHealth,
} from '@/api/endpoints/integration-health'
import type { HealthReport } from '@/api/types/integrations'
import { successFor } from './helpers'

const NOW = '2026-04-11T12:00:00Z'

// Storybook export: populated health reports for existing stories.
const mockHealthReports: HealthReport[] = [
  {
    connection_name: 'primary-github',
    status: 'healthy',
    latency_ms: 42,
    error_detail: null,
    checked_at: NOW,
    consecutive_failures: 0,
  },
  {
    connection_name: 'ops-smtp',
    status: 'unhealthy',
    latency_ms: null,
    error_detail: 'Connection refused',
    checked_at: NOW,
    consecutive_failures: 4,
  },
]

export const integrationHealthList = [
  http.get('/api/v1/integrations/health', () =>
    HttpResponse.json(
      successFor<typeof listIntegrationHealth>(mockHealthReports),
    ),
  ),
  http.get('/api/v1/integrations/health/:name', ({ params }) => {
    const report = mockHealthReports.find((r) => r.connection_name === params.name)
    return HttpResponse.json(
      successFor<typeof getSingleIntegrationHealth>(
        report ?? {
          connection_name: String(params.name),
          status: 'unknown',
          latency_ms: null,
          error_detail: null,
          checked_at: NOW,
          consecutive_failures: 0,
        },
      ),
    )
  }),
]

// Default test handlers: empty list.
export const integrationHealthHandlers = [
  http.get('/api/v1/integrations/health', () =>
    HttpResponse.json(successFor<typeof listIntegrationHealth>([])),
  ),
  http.get('/api/v1/integrations/health/:name', ({ params }) =>
    HttpResponse.json(
      successFor<typeof getSingleIntegrationHealth>({
        connection_name: String(params.name),
        status: 'unknown',
        latency_ms: null,
        error_detail: null,
        checked_at: NOW,
        consecutive_failures: 0,
      }),
    ),
  ),
]
