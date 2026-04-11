import type { Meta, StoryObj } from '@storybook/react-vite'
import { fn } from 'storybook/test'
import type { McpCatalogEntry } from '@/api/types'
import { CatalogEntryCard } from './CatalogEntryCard'

const githubEntry: McpCatalogEntry = {
  id: 'github-mcp',
  name: 'GitHub',
  description:
    'Read and write GitHub repositories, issues, pull requests, and actions',
  npm_package: '@modelcontextprotocol/server-github',
  required_connection_type: 'github',
  transport: 'stdio',
  capabilities: ['repository_access', 'issue_management', 'pull_requests', 'actions'],
  tags: ['vcs', 'collaboration', 'ci'],
}

const filesystemEntry: McpCatalogEntry = {
  id: 'filesystem-mcp',
  name: 'Filesystem',
  description: 'Read, write, and manage files on the local filesystem',
  npm_package: '@modelcontextprotocol/server-filesystem',
  required_connection_type: null,
  transport: 'stdio',
  capabilities: ['file_read', 'file_write', 'directory_listing'],
  tags: ['filesystem', 'local'],
}

const meta = {
  title: 'Pages/McpCatalog/CatalogEntryCard',
  component: CatalogEntryCard,
  tags: ['autodocs'],
  args: {
    onSelect: fn(),
    onInstall: fn(),
  },
  decorators: [
    (Story) => (
      <div className="max-w-sm">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof CatalogEntryCard>

export default meta
type Story = StoryObj<typeof meta>

export const WithConnection: Story = {
  args: { entry: githubEntry, installed: false },
}

export const Connectionless: Story = {
  args: { entry: filesystemEntry, installed: false },
}

export const Installed: Story = {
  args: { entry: githubEntry, installed: true },
}
