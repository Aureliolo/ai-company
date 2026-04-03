import type { AxiosResponse } from 'axios'
import { vi } from 'vitest'

// Mock dev auth bypass ON so the 401 interceptor skips localStorage clearing.
// Separate file because vi.mock is file-scoped and client.test.ts mocks it OFF.
vi.mock('@/utils/dev', () => ({ IS_DEV_AUTH_BYPASS: true }))

import { apiClient } from '@/api/client'

describe('apiClient 401 response interceptor (dev bypass active)', () => {
  afterEach(() => {
    localStorage.clear()
  })

  it('does NOT clear auth localStorage keys on 401 when bypass is active', async () => {
    localStorage.setItem('auth_token', 'dev-token')
    localStorage.setItem('auth_token_expires_at', '99999999')
    localStorage.setItem('auth_must_change_password', 'false')

    const error = new (await import('axios')).AxiosError(
      'Unauthorized',
      'ERR_BAD_RESPONSE',
      undefined,
      undefined,
      { status: 401, data: {}, headers: {}, statusText: 'Unauthorized', config: {} as AxiosResponse['config'] } as AxiosResponse,
    )

    await expect(apiClient.interceptors.response.handlers?.[0]?.rejected?.(error)).rejects.toBeDefined()

    // Bypass is active -- localStorage must NOT be cleared
    expect(localStorage.getItem('auth_token')).toBe('dev-token')
    expect(localStorage.getItem('auth_token_expires_at')).toBe('99999999')
    expect(localStorage.getItem('auth_must_change_password')).toBe('false')
  })
})
