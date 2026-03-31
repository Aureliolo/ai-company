import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SearchInput } from './SearchInput'

const meta: Meta<typeof SearchInput> = {
  title: 'Settings/SearchInput',
  component: SearchInput,
  parameters: { layout: 'centered', a11y: { test: 'error' } },
}
export default meta

type Story = StoryObj<typeof SearchInput>

export const Default: Story = {
  render: function Render() {
    const [value, setValue] = useState('')
    return <SearchInput value={value} onChange={setValue} className="w-64" />
  },
}

export const WithResultCount: Story = {
  render: function Render() {
    const [value, setValue] = useState('server')
    return <SearchInput value={value} onChange={setValue} className="w-64" resultCount={3} />
  },
}

export const Empty: Story = {
  args: { value: '', onChange: () => {}, className: 'w-64' },
}
