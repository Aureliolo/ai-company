import { http, HttpResponse } from 'msw'
import type { PackInfoResponse } from '@/api/types'
import { apiError, apiSuccess } from './helpers'

const mockPacks: readonly PackInfoResponse[] = [
  {
    name: 'security-team',
    display_name: 'Security Team',
    description: 'Security Engineer and Security Operations team.',
    source: 'builtin',
    tags: ['security', 'compliance'],
    agent_count: 2,
    department_count: 1,
  },
  {
    name: 'data-team',
    display_name: 'Data Team',
    description: 'Data Analyst, Data Engineer, and ML Engineer.',
    source: 'builtin',
    tags: ['data', 'analytics'],
    agent_count: 3,
    department_count: 1,
  },
  {
    name: 'qa-pipeline',
    display_name: 'QA Pipeline',
    description: 'QA Lead, QA Engineer, and Automation Engineer.',
    source: 'builtin',
    tags: ['qa', 'testing'],
    agent_count: 3,
    department_count: 1,
  },
  {
    name: 'creative-marketing',
    display_name: 'Creative & Marketing',
    description: 'Content Writer and Brand Strategist.',
    source: 'builtin',
    tags: ['creative', 'marketing'],
    agent_count: 2,
    department_count: 1,
  },
  {
    name: 'design-team',
    display_name: 'Design Team',
    description: 'UX Designer and UX Researcher.',
    source: 'builtin',
    tags: ['design', 'ux'],
    agent_count: 2,
    department_count: 1,
  },
]

export const templatePacksList = [
  http.get('*/template-packs', () => HttpResponse.json(apiSuccess(mockPacks))),
  http.post('*/template-packs/apply', async ({ request }) => {
    const body = (await request.json()) as { pack_name: string }
    const pack = mockPacks.find((p) => p.name === body.pack_name)
    if (!pack) {
      return HttpResponse.json(apiError('Pack not found'), { status: 404 })
    }
    return HttpResponse.json(
      apiSuccess({
        pack_name: pack.name,
        agents_added: pack.agent_count,
        departments_added: pack.department_count,
      }),
    )
  }),
]
