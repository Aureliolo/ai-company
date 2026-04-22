import fc from 'fast-check'
import type { AxiosResponse } from 'axios'
import { unwrap, unwrapPaginated, ApiRequestError } from '@/api/client'
import type { ApiResponse, PaginatedResponse } from '@/api/types/http'

function mockResponse<T>(data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: 'OK', headers: {}, config: {} as AxiosResponse['config'] }
}

describe('client property tests', () => {
  it('unwrap returns data for any success envelope', () => {
    fc.assert(
      fc.property(fc.anything(), (payload) => {
        // Exclude null/undefined since those are treated as error
        if (payload === null || payload === undefined) return
        const response = mockResponse<ApiResponse<unknown>>({
          data: payload,
          error: null,
          error_detail: null,
          success: true,
        })
        expect(unwrap(response)).toEqual(payload)
      }),
    )
  })

  it('unwrap throws ApiRequestError for any error envelope', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1 }), (errorMsg) => {
        const response = mockResponse<ApiResponse<null>>({
          data: null,
          error: errorMsg,
          error_detail: {
            detail: errorMsg,
            error_code: 8000,
            error_category: 'internal',
            retryable: false,
            retry_after: null,
            instance: 'test',
            title: 'Error',
            type: 'about:blank',
          },
          success: false,
        })
        expect(() => unwrap(response)).toThrow(ApiRequestError)
      }),
    )
  })

  it('unwrapPaginated returns correct structure for valid paginated envelopes', () => {
    fc.assert(
      fc.property(
        fc.array(fc.record({ id: fc.string() })),
        fc.nat({ max: 10000 }),
        fc.nat({ max: 1000 }),
        fc.integer({ min: 1, max: 200 }),
        (items, total, offset, limit) => {
          const response = mockResponse<PaginatedResponse<{ id: string }>>({
            data: items,
            error: null,
            error_detail: null,
            success: true,
            pagination: { total, offset, limit, next_cursor: null, has_more: false },
          })
          const result = unwrapPaginated(response)
          expect(result.data).toEqual(items)
          expect(result.total).toBe(total)
          expect(result.offset).toBe(offset)
          expect(result.limit).toBe(limit)
        },
      ),
    )
  })
})
