import { http, HttpResponse } from 'msw'
import type {
  getTunnelStatus,
  startTunnel,
} from '@/api/endpoints/tunnel'
import { apiSuccess, successFor, voidSuccess } from './helpers'

// ── Storybook-facing named export (stateful tunnel url for story demos). ──
const tunnelState: { url: string | null } = { url: null }

export const tunnelHandlers = [
  http.get('/api/v1/integrations/tunnel/status', () =>
    HttpResponse.json(apiSuccess({ public_url: tunnelState.url })),
  ),
  http.post('/api/v1/integrations/tunnel/start', () => {
    tunnelState.url = 'https://mock-tunnel.ngrok.io'
    return HttpResponse.json(apiSuccess({ public_url: tunnelState.url }))
  }),
  http.post('/api/v1/integrations/tunnel/stop', () => {
    tunnelState.url = null
    return HttpResponse.json(apiSuccess(null))
  }),
]

// ── Default test handlers (tunnel inactive). ──
export const tunnelDefaultHandlers = [
  http.get('/api/v1/integrations/tunnel/status', () =>
    HttpResponse.json(successFor<typeof getTunnelStatus>({ public_url: null })),
  ),
  http.post('/api/v1/integrations/tunnel/start', () =>
    HttpResponse.json(
      successFor<typeof startTunnel>({ public_url: 'https://mock-tunnel.ngrok.io' }),
    ),
  ),
  http.post('/api/v1/integrations/tunnel/stop', () => HttpResponse.json(voidSuccess())),
]
