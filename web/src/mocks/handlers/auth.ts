import { http, HttpResponse } from 'msw'
import type { AuthResponse } from '@/api/types'
import { apiSuccess } from './helpers'

const mockAuthResponse: AuthResponse = {
  expires_in: 86400,
  must_change_password: false,
}

/** POST /api/v1/auth/login -> success with mock auth response (cookie set by server). */
export const authLoginSuccess = [
  http.post('/api/v1/auth/login', () =>
    HttpResponse.json(apiSuccess(mockAuthResponse)),
  ),
]

/** POST /api/v1/auth/setup -> success with mock auth response (cookie set by server). */
export const authSetupSuccess = [
  http.post('/api/v1/auth/setup', () =>
    HttpResponse.json(apiSuccess(mockAuthResponse)),
  ),
]
