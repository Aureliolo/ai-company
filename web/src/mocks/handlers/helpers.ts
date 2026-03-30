import type { ApiResponse, ErrorDetail } from '@/api/types'

/** Build a successful ApiResponse<T> envelope for MSW handlers. */
export function apiSuccess<T>(data: T): ApiResponse<T> {
  return { data, error: null, error_detail: null, success: true }
}

/** Build a failed ApiResponse envelope for MSW handlers. */
export function apiError(
  error: string,
  overrides?: Partial<ErrorDetail>,
): ApiResponse<never> {
  return {
    data: null,
    error,
    error_detail: {
      detail: error,
      error_code: 1000,
      error_category: 'internal',
      retryable: false,
      retry_after: null,
      instance: '/storybook',
      title: 'Error',
      type: 'about:blank',
      ...overrides,
    },
    success: false,
  }
}
