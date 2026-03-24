import fc from 'fast-check'
import { AxiosError, type AxiosResponse } from 'axios'
import { getErrorMessage } from '@/utils/errors'

describe('errors property tests', () => {
  it('getErrorMessage never returns empty string', () => {
    fc.assert(
      fc.property(fc.anything(), (input) => {
        const msg = getErrorMessage(input)
        expect(msg.length).toBeGreaterThan(0)
      }),
    )
  })

  it('getErrorMessage for 5xx never leaks response body', () => {
    const statusArb = fc.integer({ min: 500, max: 599 })
    // Use identifiable strings that would never appear in generic messages
    const bodyArb = fc.stringMatching(/^[A-Z][a-z]{4,20}Error: .{5,50}$/)

    fc.assert(
      fc.property(statusArb, bodyArb, (status, body) => {
        const error = new AxiosError(
          'Request failed',
          'ERR_BAD_RESPONSE',
          undefined,
          undefined,
          {
            status,
            data: { error: body },
            headers: {},
            statusText: 'Error',
            config: {} as AxiosResponse['config'],
          } as AxiosResponse,
        )
        const msg = getErrorMessage(error)
        expect(msg).not.toContain(body)
      }),
    )
  })
})
