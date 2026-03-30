describe('getCspNonce', () => {
  afterEach(() => {
    document.querySelector('meta[name="csp-nonce"]')?.remove()
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
})
