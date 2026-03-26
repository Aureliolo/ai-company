import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ErrorFallbackProps } from '@/components/ui/error-boundary'
import { ErrorBoundary } from '@/components/ui/error-boundary'

function ThrowingComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error message')
  }
  return <div>Normal content</div>
}

/** Used by retry tests -- throws based on external flag. */
const throwFlag = { current: true }

function ConditionalThrower() {
  if (throwFlag.current) throw new Error('Boom')
  return <div>Recovered</div>
}

function CustomFallback({ error }: ErrorFallbackProps) {
  return <div>Custom: {error.message}</div>
}

// Suppress console.error from React error boundary during tests
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  throwFlag.current = true
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>All good</div>
      </ErrorBoundary>,
    )
    expect(screen.getByText('All good')).toBeInTheDocument()
  })

  it('renders default fallback when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow />
      </ErrorBoundary>,
    )
    expect(screen.queryByText('Normal content')).not.toBeInTheDocument()
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('retry button resets the error boundary', async () => {
    const user = userEvent.setup()

    render(
      <ErrorBoundary>
        <ConditionalThrower />
      </ErrorBoundary>,
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()

    // Fix the issue before retrying
    throwFlag.current = false
    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(screen.getByText('Recovered')).toBeInTheDocument()
  })

  it('calls onReset when retry is clicked', async () => {
    const user = userEvent.setup()
    const onReset = vi.fn()

    render(
      <ErrorBoundary onReset={onReset}>
        <ConditionalThrower />
      </ErrorBoundary>,
    )

    throwFlag.current = false
    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(onReset).toHaveBeenCalledTimes(1)
  })

  it('custom fallback receives error', () => {
    render(
      <ErrorBoundary fallback={CustomFallback}>
        <ThrowingComponent shouldThrow />
      </ErrorBoundary>,
    )
    expect(screen.getByText('Custom: Test error message')).toBeInTheDocument()
  })

  it('page level renders full-height layout', () => {
    const { container } = render(
      <ErrorBoundary level="page">
        <ThrowingComponent shouldThrow />
      </ErrorBoundary>,
    )
    const fallback = container.querySelector('[data-error-level="page"]')
    expect(fallback).toBeInTheDocument()
  })

  it('section level renders card-sized layout', () => {
    const { container } = render(
      <ErrorBoundary level="section">
        <ThrowingComponent shouldThrow />
      </ErrorBoundary>,
    )
    const fallback = container.querySelector('[data-error-level="section"]')
    expect(fallback).toBeInTheDocument()
  })

  it('component level renders inline layout', () => {
    const { container } = render(
      <ErrorBoundary level="component">
        <ThrowingComponent shouldThrow />
      </ErrorBoundary>,
    )
    const fallback = container.querySelector('[data-error-level="component"]')
    expect(fallback).toBeInTheDocument()
  })
})
