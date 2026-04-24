import { useRef, useState } from 'react'
import type { ComponentProps } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './button'
import { SearchInput, type SearchInputHandle } from './search-input'

const meta = {
  title: 'Forms/SearchInput',
  component: SearchInput,
  tags: ['autodocs'],
  parameters: { layout: 'padded', a11y: { test: 'error' } },
  args: {
    value: '',
    onChange: () => {},
  },
} satisfies Meta<typeof SearchInput>

export default meta
type Story = StoryObj<typeof meta>

function Controlled(args: Omit<ComponentProps<typeof SearchInput>, 'value' | 'onChange'>) {
  const [value, setValue] = useState('')
  return <SearchInput {...args} value={value} onChange={setValue} />
}

export const Default: Story = {
  render: (args) => <Controlled {...args} />,
  args: { placeholder: 'Search workflows...' },
}

export const WithFocusShortcut: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    placeholder: 'Press / to focus',
    focusShortcut: true,
  },
}

export const PrefilledValue: Story = {
  args: {
    value: 'stream-processor',
    onChange: () => {},
    placeholder: 'Search workflows...',
  },
}

export const Disabled: Story = {
  args: {
    value: 'query locked',
    onChange: () => {},
    disabled: true,
  },
}

export const NarrowWidth: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    placeholder: 'Compact search',
    maxWidth: 'narrow',
  },
}

export const WideWidth: Story = {
  render: (args) => <Controlled {...args} />,
  args: {
    placeholder: 'List-page search',
    maxWidth: 'wide',
  },
}

function ImperativeDemo() {
  const ref = useRef<SearchInputHandle | null>(null)
  const [value, setValue] = useState('hello')
  return (
    <div className="flex flex-col gap-2">
      <SearchInput
        ref={ref}
        value={value}
        onChange={setValue}
        placeholder="Imperative ref demo"
      />
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={() => ref.current?.focus()}>
          focus()
        </Button>
        <Button size="sm" variant="outline" onClick={() => ref.current?.clear()}>
          clear()
        </Button>
      </div>
    </div>
  )
}

export const ImperativeApi: Story = {
  render: () => <ImperativeDemo />,
}
