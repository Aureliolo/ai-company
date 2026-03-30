import { http, HttpResponse } from 'msw'
import type { SetupStatusResponse } from '@/api/types'
import { apiSuccess } from './helpers'

const setupComplete: SetupStatusResponse = {
  needs_admin: false,
  needs_setup: false,
  has_providers: true,
  has_name_locales: true,
  has_company: true,
  has_agents: true,
  min_password_length: 12,
}

const setupNeedsAdmin: SetupStatusResponse = {
  needs_admin: true,
  needs_setup: true,
  has_providers: false,
  has_name_locales: false,
  has_company: false,
  has_agents: false,
  min_password_length: 12,
}

/** GET /api/v1/setup/status -> setup complete (normal login flow). */
export const setupStatusComplete = [
  http.get('/api/v1/setup/status', () =>
    HttpResponse.json(apiSuccess(setupComplete)),
  ),
]

/** GET /api/v1/setup/status -> needs admin (first-run flow). */
export const setupStatusNeedsAdmin = [
  http.get('/api/v1/setup/status', () =>
    HttpResponse.json(apiSuccess(setupNeedsAdmin)),
  ),
]
