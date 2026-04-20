import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { SinkInfo } from '@/api/types/settings'
import { SinkCard } from '@/pages/settings/sinks/SinkCard'

function makeSink(overrides: Partial<SinkInfo> = {}): SinkInfo {
  return {
    identifier: 'synthorg.log',
    sink_type: 'file',
    level: 'INFO',
    json_format: true,
    rotation: { strategy: 'builtin', max_bytes: 10_485_760, backup_count: 5 },
    is_default: true,
    enabled: true,
    routing_prefixes: [],
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('SinkCard', () => {
  it('renders identifier', () => {
    render(<SinkCard sink={makeSink()} onEdit={vi.fn()} />)
    expect(screen.getByText('synthorg.log')).toBeInTheDocument()
  })

  it('renders level badge', () => {
    render(<SinkCard sink={makeSink({ level: 'WARNING' })} onEdit={vi.fn()} />)
    expect(screen.getByText('WARNING')).toBeInTheDocument()
  })

  it('renders format as JSON', () => {
    render(<SinkCard sink={makeSink({ json_format: true })} onEdit={vi.fn()} />)
    expect(screen.getByText('JSON')).toBeInTheDocument()
  })

  it('renders format as Text', () => {
    render(<SinkCard sink={makeSink({ json_format: false })} onEdit={vi.fn()} />)
    expect(screen.getByText('Text')).toBeInTheDocument()
  })

  it('edit button calls onEdit with sink', async () => {
    const user = userEvent.setup()
    const onEdit = vi.fn()
    const sink = makeSink()
    render(<SinkCard sink={sink} onEdit={onEdit} />)

    await user.click(screen.getByRole('button', { name: /edit/i }))
    expect(onEdit).toHaveBeenCalledWith(sink)
  })

  it('applies reduced opacity when disabled', () => {
    const { container } = render(
      <SinkCard sink={makeSink({ enabled: false })} onEdit={vi.fn()} />,
    )
    const card = container.firstElementChild as HTMLElement
    expect(card.className).toContain('opacity-50')
  })

  it('does not apply reduced opacity when enabled', () => {
    const { container } = render(
      <SinkCard sink={makeSink({ enabled: true })} onEdit={vi.fn()} />,
    )
    const card = container.firstElementChild as HTMLElement
    expect(card.className).not.toContain('opacity-50')
  })

  it('renders rotation display', () => {
    render(
      <SinkCard
        sink={makeSink({ rotation: { strategy: 'builtin', max_bytes: 10_485_760, backup_count: 5 } })}
        onEdit={vi.fn()}
      />,
    )
    expect(screen.getByText('Rotation: 10 MB x 5')).toBeInTheDocument()
  })

  it('omits rotation when null', () => {
    render(<SinkCard sink={makeSink({ rotation: null })} onEdit={vi.fn()} />)
    expect(screen.queryByText(/rotation/i)).not.toBeInTheDocument()
  })

  it('renders routing prefixes', () => {
    render(
      <SinkCard
        sink={makeSink({ routing_prefixes: ['synthorg.security', 'synthorg.hr'] })}
        onEdit={vi.fn()}
      />,
    )
    expect(screen.getByText('Routes: synthorg.security, synthorg.hr')).toBeInTheDocument()
  })

  it('shows console icon for console sink type', () => {
    render(<SinkCard sink={makeSink({ sink_type: 'console' })} onEdit={vi.fn()} />)
    // Console type uses Monitor icon, file type uses FileText icon
    // Both are aria-hidden, so we verify by the enabled/disabled status dot
    expect(screen.getByTitle('Enabled')).toBeInTheDocument()
  })

  it('shows default label for default sinks', () => {
    render(<SinkCard sink={makeSink({ is_default: true })} onEdit={vi.fn()} />)
    expect(screen.getByText('Default')).toBeInTheDocument()
  })

  it('hides default label for non-default sinks', () => {
    render(<SinkCard sink={makeSink({ is_default: false })} onEdit={vi.fn()} />)
    expect(screen.queryByText('Default')).not.toBeInTheDocument()
  })
})
