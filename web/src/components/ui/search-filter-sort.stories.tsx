import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { Button } from './button'
import { SearchFilterSort } from './search-filter-sort'
import { SearchInput } from './search-input'
import { SelectField } from './select-field'

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
  const [dept, setDept] = useState('all')
  const [status, setStatus] = useState('all')
  const [sort, setSort] = useState('name')
  return (
    <SearchFilterSort
      search={<SearchInput value={search} onChange={setSearch} placeholder="Search agents..." ariaLabel="Search agents" />}
      filters={
        <>
          <SelectField
            label="Department"
            value={dept}
            onChange={setDept}
            options={[
              { value: 'all', label: 'All departments' },
              { value: 'eng', label: 'Engineering' },
              { value: 'design', label: 'Design' },
            ]}
          />
          <SelectField
            label="Status"
            value={status}
            onChange={setStatus}
            options={[
              { value: 'all', label: 'All statuses' },
              { value: 'active', label: 'Active' },
              { value: 'idle', label: 'Idle' },
            ]}
          />
        </>
      }
      sort={
        <SelectField
          label="Sort"
          value={sort}
          onChange={setSort}
          options={[
            { value: 'name', label: 'Sort: Name' },
            { value: 'level', label: 'Sort: Level' },
          ]}
        />
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
  const [risk, setRisk] = useState('all')
  return (
    <SearchFilterSort
      search={<SearchInput value={search} onChange={setSearch} placeholder="Search approvals..." ariaLabel="Search approvals" />}
      filters={
        <SelectField
          label="Risk"
          value={risk}
          onChange={setRisk}
          options={[
            { value: 'all', label: 'All risk levels' },
            { value: 'critical', label: 'Critical' },
            { value: 'high', label: 'High' },
          ]}
        />
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
