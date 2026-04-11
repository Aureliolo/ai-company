import { useTunnelStore } from '@/stores/tunnel'

vi.mock('@/api/endpoints/tunnel', () => ({
  getTunnelStatus: vi.fn(),
  startTunnel: vi.fn(),
  stopTunnel: vi.fn(),
}))

const { getTunnelStatus, startTunnel, stopTunnel } = await import(
  '@/api/endpoints/tunnel'
)

describe('useTunnelStore', () => {
  beforeEach(() => {
    useTunnelStore.getState().reset()
    vi.clearAllMocks()
  })

  it('maps status.public_url to the running phase', async () => {
    vi.mocked(getTunnelStatus).mockResolvedValue({
      public_url: 'https://abc.ngrok.io',
    })
    await useTunnelStore.getState().fetchStatus()
    expect(useTunnelStore.getState().phase).toBe('on')
    expect(useTunnelStore.getState().publicUrl).toBe('https://abc.ngrok.io')
  })

  it('transitions to the stopped phase when no URL is returned', async () => {
    vi.mocked(getTunnelStatus).mockResolvedValue({ public_url: null })
    await useTunnelStore.getState().fetchStatus()
    expect(useTunnelStore.getState().phase).toBe('stopped')
  })

  it('transitions to error phase when the status fetch fails', async () => {
    vi.mocked(getTunnelStatus).mockRejectedValue(new Error('fetch boom'))
    await useTunnelStore.getState().fetchStatus()
    const state = useTunnelStore.getState()
    expect(state.phase).toBe('error')
    expect(state.error).toBe('fetch boom')
    expect(state.publicUrl).toBeNull()
  })

  it('start transitions enabling -> on on success', async () => {
    vi.mocked(startTunnel).mockResolvedValue({
      public_url: 'https://new.ngrok.io',
    })
    await useTunnelStore.getState().start()
    expect(useTunnelStore.getState().phase).toBe('on')
    expect(useTunnelStore.getState().publicUrl).toBe('https://new.ngrok.io')
  })

  it('start moves to error phase on failure', async () => {
    vi.mocked(startTunnel).mockRejectedValue(new Error('ngrok down'))
    await useTunnelStore.getState().start()
    expect(useTunnelStore.getState().phase).toBe('error')
    expect(useTunnelStore.getState().error).toBe('ngrok down')
  })

  it('stop clears the URL on success', async () => {
    useTunnelStore.setState({ phase: 'on', publicUrl: 'https://abc.ngrok.io' })
    vi.mocked(stopTunnel).mockResolvedValue(undefined)
    await useTunnelStore.getState().stop()
    expect(useTunnelStore.getState().phase).toBe('stopped')
    expect(useTunnelStore.getState().publicUrl).toBeNull()
  })
})
