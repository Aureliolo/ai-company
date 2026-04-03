import type { AxiosResponse } from 'axios'
import { vi } from 'vitest'

// Mock dev auth bypass OFF so the 401 interceptor actually clears localStorage.
// Must be hoisted before client.ts imports @/utils/dev at module level.
vi.mock('@/utils/dev', () => ({ IS_DEV_AUTH_BYPASS: false }))

import { ApiRequestError, unwrap, unwrapPaginated, unwrapVoid, apiClient } from '@/api/client'
import type { ApiResponse, ErrorDetail, PaginatedResponse } from '@/api/types'

function mockResponse<T>(data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: 'OK', headers: {}, config: {} as AxiosResponse['config'] }
}

const testErrorDetail: ErrorDetail = {
  detail: 'Resource not found',
  error_code: 3000,
  error_category: 'not_found',
  retryable: false,
  retry_after: null,
  instance: 'req-abc',
  title: 'Not Found',
  type: 'https://docs.example.com/errors/not-found',
}

describe('ApiRequestError', () => {
  it('sets name and message', () => {
    const err = new ApiRequestError('test error')
    expect(err.name).toBe('ApiRequestError')
    expect(err.message).toBe('test error')
    expect(err.errorDetail).toBeNull()
  })

  it('carries error detail', () => {
    const err = new ApiRequestError('test', testErrorDetail)
    expect(err.errorDetail).toEqual(testErrorDetail)
  })

  it('is an instance of Error', () => {
    const err = new ApiRequestError('test')
    expect(err).toBeInstanceOf(Error)
  })
})

describe('unwrap', () => {
  it('extracts data from success response', () => {
    const response = mockResponse<ApiResponse<{ id: string }>>({
      data: { id: 'test-1' },
      error: null,
      error_detail: null,
      success: true,
    })
    expect(unwrap(response)).toEqual({ id: 'test-1' })
  })

  it('throws for success:true with data:null', () => {
    const response = mockResponse<ApiResponse<null>>({
      data: null,
      error: null,
      error_detail: null,
      success: true,
    })
    expect(() => unwrap(response)).toThrow(ApiRequestError)
  })

  it('throws ApiRequestError for error response', () => {
    const response = mockResponse<ApiResponse<null>>({
      data: null,
      error: 'Something went wrong',
      error_detail: testErrorDetail,
      success: false,
    })
    expect(() => unwrap(response)).toThrow(ApiRequestError)
    try {
      unwrap(response)
    } catch (err) {
      const caught = err as ApiRequestError
      expect(caught.message).toBe('Something went wrong')
      expect(caught.errorDetail).toEqual(testErrorDetail)
    }
  })

  it('throws for null body', () => {
    const response = mockResponse(null)
    expect(() => unwrap(response as unknown as AxiosResponse<ApiResponse<unknown>>)).toThrow('Unknown API error')
  })

  it('throws for non-object body', () => {
    const response = mockResponse('not an object')
    expect(() => unwrap(response as unknown as AxiosResponse<ApiResponse<unknown>>)).toThrow('Unknown API error')
  })

  it('throws for success=false with null error', () => {
    const response = mockResponse<ApiResponse<null>>({
      data: null,
      error: null as unknown as string,
      error_detail: null as unknown as ErrorDetail,
      success: false,
    })
    expect(() => unwrap(response)).toThrow('Unknown API error')
  })
})

describe('unwrapVoid', () => {
  it('does not throw for success response', () => {
    const response = mockResponse<ApiResponse<null>>({
      data: null,
      error: null,
      error_detail: null,
      success: true,
    })
    expect(() => unwrapVoid(response)).not.toThrow()
  })

  it('handles 204 No Content with empty body', () => {
    const response = { data: '' as unknown as ApiResponse<null>, status: 204, statusText: 'No Content', headers: {}, config: {} as AxiosResponse['config'] }
    expect(() => unwrapVoid(response)).not.toThrow()
  })

  it('throws ApiRequestError for error response', () => {
    const response = mockResponse<ApiResponse<null>>({
      data: null,
      error: 'Failed',
      error_detail: testErrorDetail,
      success: false,
    })
    expect(() => unwrapVoid(response)).toThrow(ApiRequestError)
  })
})

describe('unwrapPaginated', () => {
  it('extracts data and pagination from success response', () => {
    const response = mockResponse<PaginatedResponse<{ id: string }>>({
      data: [{ id: 'a' }, { id: 'b' }],
      error: null,
      error_detail: null,
      success: true,
      pagination: { total: 10, offset: 0, limit: 50 },
    })
    const result = unwrapPaginated(response)
    expect(result.data).toHaveLength(2)
    expect(result.total).toBe(10)
    expect(result.offset).toBe(0)
    expect(result.limit).toBe(50)
  })

  it('throws ApiRequestError for error response', () => {
    const response = mockResponse<PaginatedResponse<unknown>>({
      data: null,
      error: 'Error occurred',
      error_detail: testErrorDetail,
      success: false,
      pagination: null,
    })
    expect(() => unwrapPaginated(response)).toThrow(ApiRequestError)
  })

  it('throws for missing pagination', () => {
    const response = mockResponse({
      data: [],
      error: null,
      error_detail: null,
      success: true,
      pagination: null,
    })
    expect(() => unwrapPaginated(response as unknown as AxiosResponse<PaginatedResponse<unknown>>)).toThrow('Unexpected API response format')
  })

  it('throws for non-array data', () => {
    const response = mockResponse({
      data: 'not-array',
      error: null,
      error_detail: null,
      success: true,
      pagination: { total: 0, offset: 0, limit: 50 },
    })
    expect(() => unwrapPaginated(response as unknown as AxiosResponse<PaginatedResponse<unknown>>)).toThrow('Unexpected API response format')
  })
})

/** Extract the fulfilled handler from the first request interceptor -- throws if not found. */
function getRequestInterceptor(): (config: Record<string, unknown>) => Record<string, unknown> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handlers = (apiClient.interceptors.request as any).handlers as Array<{ fulfilled?: (config: any) => any }> | undefined
  const fulfilled = handlers?.[0]?.fulfilled
  if (!fulfilled) throw new Error('Request interceptor not found -- Axios internals may have changed')
  return fulfilled as (config: Record<string, unknown>) => Record<string, unknown>
}

describe('apiClient request interceptor', () => {
  afterEach(() => {
    localStorage.removeItem('auth_token')
  })

  it('injects auth token when present in localStorage', () => {
    localStorage.setItem('auth_token', 'test-jwt-token')
    const fulfilled = getRequestInterceptor()
    const result = fulfilled({ headers: {} }) as { headers: Record<string, string> }
    expect(result.headers['Authorization']).toBe('Bearer test-jwt-token')
  })

  it('does not inject token when not in localStorage', () => {
    localStorage.removeItem('auth_token')
    const fulfilled = getRequestInterceptor()
    const result = fulfilled({ headers: {} }) as { headers: Record<string, string> }
    expect(result.headers['Authorization']).toBeUndefined()
  })
})

describe('apiClient 401 response interceptor', () => {
  afterEach(() => {
    localStorage.clear()
  })

  it('clears auth localStorage keys on 401', async () => {
    localStorage.setItem('auth_token', 'old-token')
    localStorage.setItem('auth_token_expires_at', '99999999')
    localStorage.setItem('auth_must_change_password', 'true')

    const error = new (await import('axios')).AxiosError(
      'Unauthorized',
      'ERR_BAD_RESPONSE',
      undefined,
      undefined,
      { status: 401, data: {}, headers: {}, statusText: 'Unauthorized', config: {} as AxiosResponse['config'] } as AxiosResponse,
    )

    // The interceptor rejects with the error but clears localStorage as a side effect
    await expect(apiClient.interceptors.response.handlers?.[0]?.rejected?.(error)).rejects.toBeDefined()

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('auth_token_expires_at')).toBeNull()
    expect(localStorage.getItem('auth_must_change_password')).toBeNull()
  })

  it('passes through non-401 errors unchanged', async () => {
    const error = new (await import('axios')).AxiosError(
      'Server Error',
      'ERR_BAD_RESPONSE',
      undefined,
      undefined,
      { status: 500, data: {}, headers: {}, statusText: 'Error', config: {} as AxiosResponse['config'] } as AxiosResponse,
    )

    localStorage.setItem('auth_token', 'should-remain')

    await expect(apiClient.interceptors.response.handlers?.[0]?.rejected?.(error)).rejects.toBeDefined()

    // Token should NOT be cleared on non-401
    expect(localStorage.getItem('auth_token')).toBe('should-remain')
  })
})
