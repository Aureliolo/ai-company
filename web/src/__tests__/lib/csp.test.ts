describe('getCspNonce', () => {
  afterEach(() => {
    document
      .querySelectorAll('meta[name="csp-nonce"]')
      .forEach((el) => el.remove())
    vi.restoreAllMocks()
    vi.resetModules()
  })

  it('returns undefined when no meta tag exists', async () => {
    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBeUndefined()
  })

  it('reads nonce from meta tag', async () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'abc123'
    document.head.appendChild(meta)

    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBe('abc123')
  })

  it('caches the value across calls', async () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'first'
    document.head.appendChild(meta)

    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBe('first')

    // Change content after first read -- should still return cached value
    meta.content = 'second'
    expect(getCspNonce()).toBe('first')
  })

  it('returns undefined for empty content', async () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = ''
    document.head.appendChild(meta)

    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBeUndefined()
  })

  it('returns undefined for whitespace-only content', async () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = '   '
    document.head.appendChild(meta)

    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBeUndefined()
  })

  it('returns undefined for un-substituted Caddy template placeholder', async () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = '{{placeholder "http.request.uuid"}}'
    document.head.appendChild(meta)

    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBeUndefined()
  })

  it('trims whitespace from valid nonce values', async () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = '  abc123  '
    document.head.appendChild(meta)

    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBe('abc123')
  })

  it('caches absent result and does not re-query DOM', async () => {
    const spy = vi.spyOn(document, 'querySelector')

    const { getCspNonce } = await import('@/lib/csp')
    expect(getCspNonce()).toBeUndefined()
    expect(getCspNonce()).toBeUndefined()

    // querySelector called once on first getCspNonce() call.
    // Subsequent calls hit the cache, so no additional DOM queries.
    const cspCalls = spy.mock.calls.filter(
      ([sel]) => sel === 'meta[name="csp-nonce"]',
    )
    expect(cspCalls).toHaveLength(1)
  })
})
