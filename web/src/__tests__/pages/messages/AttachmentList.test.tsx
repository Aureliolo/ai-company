import { render, screen } from '@testing-library/react'
import { AttachmentList } from '@/pages/messages/AttachmentList'

describe('AttachmentList', () => {
  it('renders nothing for empty attachments', () => {
    const { container } = render(<AttachmentList attachments={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders attachment references', () => {
    render(<AttachmentList attachments={[{ type: 'artifact', ref: 'pr-42' }]} />)
    expect(screen.getByText('pr-42')).toBeInTheDocument()
  })

  it('renders multiple attachments', () => {
    render(<AttachmentList attachments={[
      { type: 'artifact', ref: 'pr-42' },
      { type: 'file', ref: 'report.pdf' },
      { type: 'link', ref: 'https://example.com' },
    ]} />)
    expect(screen.getByText('pr-42')).toBeInTheDocument()
    expect(screen.getByText('report.pdf')).toBeInTheDocument()
    expect(screen.getByText('https://example.com')).toBeInTheDocument()
  })

  it('renders different icons per attachment type', () => {
    const { container } = render(<AttachmentList attachments={[
      { type: 'artifact', ref: 'a' },
      { type: 'file', ref: 'b' },
      { type: 'link', ref: 'c' },
    ]} />)
    // Each attachment has an SVG icon
    const svgs = container.querySelectorAll('svg')
    expect(svgs).toHaveLength(3)
  })
})
