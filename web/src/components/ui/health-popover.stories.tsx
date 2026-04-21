import type { Meta, StoryObj } from '@storybook/react'
import { http, HttpResponse } from 'msw'
import type { getHealth } from '@/api/endpoints/health'
import { successFor } from '@/mocks/handlers/helpers'
import { Button } from './button'
import { HealthPopover } from './health-popover'

const meta = {
  title: 'Overlays/HealthPopover',
  component: HealthPopover,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
} satisfies Meta<typeof HealthPopover>

export default meta
type Story = StoryObj<typeof meta>

const BASE_PAYLOAD = {
  status: 'ok' as const,
  persistence: true,
  message_bus: true,
  telemetry: 'disabled' as const,
  version: '0.6.4',
  uptime_seconds: 847_200,
}

export const AllSystemsOk: Story = {
  args: {
    children: <Button size="sm">All systems normal</Button>,
  },
  parameters: {
    msw: {
      handlers: [
        http.get('/api/v1/health', () =>
          HttpResponse.json(successFor<typeof getHealth>(BASE_PAYLOAD)),
        ),
      ],
    },
  },
}

export const Degraded: Story = {
  args: {
    children: <Button size="sm">System degraded</Button>,
  },
  parameters: {
    msw: {
      handlers: [
        http.get('/api/v1/health', () =>
          HttpResponse.json(
            successFor<typeof getHealth>({
              ...BASE_PAYLOAD,
              status: 'degraded',
              message_bus: false,
            }),
          ),
        ),
      ],
    },
  },
}

export const Down: Story = {
  args: {
    children: <Button size="sm">System down</Button>,
  },
  parameters: {
    msw: {
      handlers: [
        http.get('/api/v1/health', () =>
          HttpResponse.json(
            successFor<typeof getHealth>({
              ...BASE_PAYLOAD,
              status: 'down',
              persistence: false,
              message_bus: false,
            }),
          ),
        ),
      ],
    },
  },
}

export const LoadError: Story = {
  args: {
    children: <Button size="sm">Health unavailable</Button>,
  },
  parameters: {
    msw: {
      handlers: [
        http.get('/api/v1/health', () =>
          HttpResponse.json({ error: 'temporary unavailability' }, { status: 503 }),
        ),
      ],
    },
  },
}

export const Loading: Story = {
  args: {
    children: <Button size="sm">Fetching health...</Button>,
  },
  parameters: {
    msw: {
      handlers: [
        http.get('/api/v1/health', async () => {
          await new Promise((resolve) => { setTimeout(resolve, 10_000) })
          return HttpResponse.json(successFor<typeof getHealth>(BASE_PAYLOAD))
        }),
      ],
    },
  },
}
