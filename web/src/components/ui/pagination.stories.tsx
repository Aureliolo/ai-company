import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { Pagination } from './pagination'

const meta = {
  title: 'Navigation/Pagination',
  component: Pagination,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
} satisfies Meta<typeof Pagination>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    page: 3,
    pageSize: 20,
    total: 247,
    onPageChange: () => {},
    onPageSizeChange: () => {},
  },
}

export const FirstPage: Story = {
  args: {
    page: 1,
    pageSize: 20,
    total: 100,
    onPageChange: () => {},
    onPageSizeChange: () => {},
  },
}

export const LastPage: Story = {
  args: {
    page: 5,
    pageSize: 20,
    total: 100,
    onPageChange: () => {},
    onPageSizeChange: () => {},
  },
}

export const SinglePage: Story = {
  args: {
    page: 1,
    pageSize: 20,
    total: 8,
    onPageChange: () => {},
    onPageSizeChange: () => {},
  },
}

export const EmptyList: Story = {
  args: {
    page: 1,
    pageSize: 20,
    total: 0,
    onPageChange: () => {},
    onPageSizeChange: () => {},
  },
}

export const LargeCount: Story = {
  args: {
    page: 42,
    pageSize: 50,
    total: 12543,
    onPageChange: () => {},
    onPageSizeChange: () => {},
  },
}

export const CursorMode: Story = {
  args: {
    page: 2,
    pageSize: 50,
    total: undefined,
    onPageChange: () => {},
  },
}

export const WithoutPageSize: Story = {
  args: {
    page: 1,
    pageSize: 20,
    total: 80,
    onPageChange: () => {},
    hidePageSize: true,
  },
}

function InteractiveDemo() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  return (
    <Pagination
      page={page}
      pageSize={pageSize}
      total={247}
      onPageChange={setPage}
      onPageSizeChange={(n) => { setPageSize(n); setPage(1) }}
    />
  )
}

export const Interactive: Story = {
  args: {
    page: 1, pageSize: 20, total: 247, onPageChange: () => {}, onPageSizeChange: () => {},
  },
  render: () => <InteractiveDemo />,
}
