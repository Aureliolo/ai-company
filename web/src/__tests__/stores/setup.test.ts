import { http, HttpResponse } from 'msw'
import { useSetupStore } from '@/stores/setup'
import { apiError, apiSuccess } from '@/mocks/handlers'
import { server } from '@/test-setup'

function resetStore() {
  useSetupStore.setState({
    setupComplete: null,
    loading: false,
    error: false,
  })
}

describe('setup store', () => {
  beforeEach(() => {
    resetStore()
  })

  it('initializes with null setupComplete, not loading, and no error', () => {
    const state = useSetupStore.getState()
    expect(state.setupComplete).toBeNull()
    expect(state.loading).toBe(false)
    expect(state.error).toBe(false)
  })

  it('fetches setup status and sets setupComplete to true when needs_setup is false', async () => {
    let calls = 0
    server.use(
      http.get('/api/v1/setup/status', () => {
        calls += 1
        return HttpResponse.json(
          apiSuccess({
            needs_admin: false,
            needs_setup: false,
            has_providers: true,
            has_name_locales: true,
            has_company: true,
            has_agents: true,
            min_password_length: 12,
          }),
        )
      }),
    )

    await useSetupStore.getState().fetchSetupStatus()

    const state = useSetupStore.getState()
    expect(state.setupComplete).toBe(true)
    expect(state.loading).toBe(false)
    expect(calls).toBe(1)
  })

  it('fetches setup status and sets setupComplete to false when needs_setup is true', async () => {
    server.use(
      http.get('/api/v1/setup/status', () =>
        HttpResponse.json(
          apiSuccess({
            needs_admin: true,
            needs_setup: true,
            has_providers: false,
            has_name_locales: false,
            has_company: false,
            has_agents: false,
            min_password_length: 12,
          }),
        ),
      ),
    )

    await useSetupStore.getState().fetchSetupStatus()

    const state = useSetupStore.getState()
    expect(state.setupComplete).toBe(false)
    expect(state.loading).toBe(false)
  })

  it('prevents concurrent fetches', async () => {
    let calls = 0
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.get('/api/v1/setup/status', async () => {
        calls += 1
        await gate
        return HttpResponse.json(
          apiSuccess({
            needs_admin: false,
            needs_setup: false,
            has_providers: true,
            has_name_locales: true,
            has_company: true,
            has_agents: true,
            min_password_length: 12,
          }),
        )
      }),
    )

    const p1 = useSetupStore.getState().fetchSetupStatus()
    expect(useSetupStore.getState().loading).toBe(true)

    const p2 = useSetupStore.getState().fetchSetupStatus()

    release()
    await p1
    await p2

    expect(calls).toBe(1)
  })

  it('sets error flag and leaves setupComplete as null on fetch error', async () => {
    server.use(
      http.get('/api/v1/setup/status', () =>
        HttpResponse.json(apiError('Network error')),
      ),
    )

    await useSetupStore.getState().fetchSetupStatus()

    const state = useSetupStore.getState()
    expect(state.setupComplete).toBeNull()
    expect(state.loading).toBe(false)
    expect(state.error).toBe(true)
  })

  it('clears error flag on retry', async () => {
    let call = 0
    server.use(
      http.get('/api/v1/setup/status', () => {
        call += 1
        if (call === 1) {
          return HttpResponse.json(apiError('Network error'))
        }
        return HttpResponse.json(
          apiSuccess({
            needs_admin: false,
            needs_setup: false,
            has_providers: true,
            has_name_locales: true,
            has_company: true,
            has_agents: true,
            min_password_length: 12,
          }),
        )
      }),
    )

    await useSetupStore.getState().fetchSetupStatus()
    expect(useSetupStore.getState().error).toBe(true)

    await useSetupStore.getState().fetchSetupStatus()

    const state = useSetupStore.getState()
    expect(state.error).toBe(false)
    expect(state.setupComplete).toBe(true)
  })
})
