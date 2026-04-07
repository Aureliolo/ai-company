import type { AxiosResponse } from 'axios'
import { vi } from 'vitest'

// Mock dev auth bypass ON so the 401 interceptor skips auth cleanup.
// Separate file because vi.mock is file-scoped and client.test.ts mocks it OFF.
vi.mock('@/utils/dev', () => ({ IS_DEV_AUTH_BYPASS: true }))

const handleUnauthorizedSpy = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: { getState: () => ({ handleUnauthorized: handleUnauthorizedSpy }) },
}))

import { apiClient } from '@/api/client'

describe('apiClient 401 response interceptor (dev bypass active)', () => {
  beforeEach(() => {
    handleUnauthorizedSpy.mockClear()
  })

  it('does NOT trigger auth cleanup on 401 when bypass is active', async () => {
    const error = new (await import('axios')).AxiosError(
      'Unauthorized',
      'ERR_BAD_RESPONSE',
      undefined,
      undefined,
      { status: 401, data: {}, headers: {}, statusText: 'Unauthorized', config: {} as AxiosResponse['config'] } as AxiosResponse,
    )

    // The interceptor should reject without triggering handleUnauthorized
    await expect(apiClient.interceptors.response.handlers?.[0]?.rejected?.(error)).rejects.toBeDefined()
    expect(handleUnauthorizedSpy).not.toHaveBeenCalled()
  })
})
