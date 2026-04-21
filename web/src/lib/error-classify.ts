import { isAxiosError, getErrorMessage } from '@/utils/errors'

export interface ClassifiedError {
  message: string
  /** HTTP status if available (server-side error). */
  status?: number
  /** Transient failures that retry may resolve (5xx, timeout, network). */
  isTransient: boolean
  /** Client-caused errors (4xx) that typically require user action. */
  isClient: boolean
  /** Whether automatic retry is advisable. */
  retryable: boolean
  /** When classified as `client`, an optional action hint (e.g. "Check your permissions"). */
  guidance?: string
}

/**
 * Classify an error into transient / client / unknown categories so the UI
 * can choose between "Retry" (transient) vs "Check configuration" (client)
 * affordances. Used by onboarding surfaces and list-fetch error banners.
 */
export function classifyError(error: unknown): ClassifiedError {
  const message = getErrorMessage(error)

  if (isAxiosError(error)) {
    const status = error.response?.status

    // Network-level failures have no response.
    if (!error.response) {
      return {
        message,
        isTransient: true,
        isClient: false,
        retryable: true,
        guidance: 'Check your network connection and try again.',
      }
    }

    if (status !== undefined && status >= 500) {
      return {
        message,
        status,
        isTransient: true,
        isClient: false,
        retryable: true,
      }
    }

    if (status === 408 || status === 429) {
      return {
        message,
        status,
        isTransient: true,
        isClient: false,
        retryable: true,
        guidance: status === 429 ? 'Rate limited. Wait a moment before retrying.' : undefined,
      }
    }

    if (status === 401) {
      return {
        message,
        status,
        isTransient: false,
        isClient: true,
        retryable: false,
        guidance: 'Your session may have expired. Please sign in again.',
      }
    }

    if (status === 403) {
      return {
        message,
        status,
        isTransient: false,
        isClient: true,
        retryable: false,
        guidance: 'You do not have permission for this action. Contact an administrator.',
      }
    }

    if (status === 404) {
      return {
        message,
        status,
        isTransient: false,
        isClient: true,
        retryable: false,
        guidance: 'The requested resource was not found. It may have been deleted.',
      }
    }

    if (status === 409) {
      return {
        message,
        status,
        isTransient: false,
        isClient: true,
        retryable: true,
        guidance: 'Someone else modified this resource. Refresh and try again.',
      }
    }

    if (status !== undefined && status >= 400 && status < 500) {
      return {
        message,
        status,
        isTransient: false,
        isClient: true,
        retryable: false,
        guidance: 'Check your input and try again.',
      }
    }
  }

  // Non-axios errors (TypeError, SyntaxError, ...) default to non-retryable.
  return {
    message,
    isTransient: false,
    isClient: false,
    retryable: false,
  }
}
