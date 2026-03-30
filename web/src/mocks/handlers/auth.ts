import { http, HttpResponse } from 'msw'
import type { TokenResponse } from '@/api/types'
import { apiSuccess } from './helpers'

const mockToken: TokenResponse = {
  token: 'mock-jwt-token-for-storybook',
  expires_in: 86400,
  must_change_password: false,
}

/** POST /api/v1/auth/login -> success with mock token. */
export const authLoginSuccess = [
  http.post('/api/v1/auth/login', () =>
    HttpResponse.json(apiSuccess(mockToken)),
  ),
]

/** POST /api/v1/auth/setup -> success with mock token. */
export const authSetupSuccess = [
  http.post('/api/v1/auth/setup', () =>
    HttpResponse.json(apiSuccess(mockToken)),
  ),
]
