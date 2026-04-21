import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { Button } from './button'
import { SearchFilterSort } from './search-filter-sort'
import { SearchInput } from './search-input'

const meta = {
  title: 'Layout/SearchFilterSort',
  component: SearchFilterSort,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
} satisfies Meta<typeof SearchFilterSort>

export default meta
type Story = StoryObj<typeof meta>

function SearchOnlyDemo() {
  const [search, setSearch] = useState('')
  return (
    <SearchFilterSort
      search={
        <SearchInput value={search} onChange={setSearch} placeholder="Search tasks..." ariaLabel="Search tasks" />
      }
    />
  )
}

export const SearchOnly: Story = {
  args: {},
  render: () => <SearchOnlyDemo />,
}

function FullRowDemo() {
  const [search, setSearch] = useState('')
  return (
    <SearchFilterSort
      search={<SearchInput value={search} onChange={setSearch} placeholder="Search agents..." ariaLabel="Search agents" />}
      filters={
        <>
          <select className="h-9 rounded-lg border border-border bg-card px-3 text-sm" aria-label="Department">
            <option>All departments</option>
            <option>Engineering</option>
            <option>Design</option>
          </select>
          <select className="h-9 rounded-lg border border-border bg-card px-3 text-sm" aria-label="Status">
            <option>All statuses</option>
            <option>Active</option>
            <option>Idle</option>
          </select>
        </>
      }
      sort={
        <select className="h-9 rounded-lg border border-border bg-card px-3 text-sm" aria-label="Sort">
          <option>Sort: Name</option>
          <option>Sort: Level</option>
        </select>
      }
    />
  )
}

export const FullRow: Story = {
  args: {},
  render: () => <FullRowDemo />,
}

function WithBatchActionsDemo() {
  const [search, setSearch] = useState('')
  return (
    <SearchFilterSort
      search={<SearchInput value={search} onChange={setSearch} placeholder="Search approvals..." ariaLabel="Search approvals" />}
      filters={
        <select className="h-9 rounded-lg border border-border bg-card px-3 text-sm" aria-label="Risk">
          <option>All risk levels</option>
          <option>Critical</option>
          <option>High</option>
        </select>
      }
      trailing={<Button size="sm">3 selected</Button>}
    />
  )
}

export const WithTrailing: Story = {
  args: {},
  render: () => <WithBatchActionsDemo />,
}

function SlashShortcutDemo() {
  const [search, setSearch] = useState('')
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Press <kbd className="rounded border border-border bg-surface px-1 py-0.5 text-[10px]">/</kbd> anywhere on the page to focus the search.
      </p>
      <SearchFilterSort
        search={<SearchInput value={search} onChange={setSearch} placeholder="Press / to focus" focusShortcut ariaLabel="Demo search" />}
      />
    </div>
  )
}

export const SlashShortcut: Story = {
  args: {},
  render: () => <SlashShortcutDemo />,
}
