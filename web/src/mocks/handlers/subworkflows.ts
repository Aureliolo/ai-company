import { http, HttpResponse } from 'msw'
import type {
  createSubworkflow,
  getVersion,
  listParents,
  listSubworkflows,
  listVersions,
  searchSubworkflows,
} from '@/api/endpoints/subworkflows'
import type { WorkflowDefinition } from '@/api/types'
import { successFor, voidSuccess } from './helpers'

function buildWorkflow(
  overrides: Partial<WorkflowDefinition> = {},
): WorkflowDefinition {
  return {
    id: 'workflow-default',
    name: 'Default Workflow',
    description: '',
    workflow_type: 'default',
    version: '1',
    inputs: [],
    outputs: [],
    is_subworkflow: true,
    nodes: [],
    edges: [],
    created_by: 'user-1',
    created_at: '2026-04-19T00:00:00Z',
    updated_at: '2026-04-19T00:00:00Z',
    revision: 1,
    ...overrides,
  }
}

export const subworkflowsHandlers = [
  http.get('/api/v1/subworkflows', () =>
    HttpResponse.json(successFor<typeof listSubworkflows>([])),
  ),
  http.get('/api/v1/subworkflows/search', () =>
    HttpResponse.json(successFor<typeof searchSubworkflows>([])),
  ),
  http.get('/api/v1/subworkflows/:id/versions', () =>
    HttpResponse.json(successFor<typeof listVersions>([])),
  ),
  http.get('/api/v1/subworkflows/:id/versions/:version', ({ params }) =>
    HttpResponse.json(
      successFor<typeof getVersion>(
        buildWorkflow({
          id: String(params.id),
          version: String(params.version),
        }),
      ),
    ),
  ),
  http.get('/api/v1/subworkflows/:id/versions/:version/parents', () =>
    HttpResponse.json(successFor<typeof listParents>([])),
  ),
  http.post('/api/v1/subworkflows', async ({ request }) => {
    const body = (await request.json()) as { name: string }
    return HttpResponse.json(
      successFor<typeof createSubworkflow>(buildWorkflow({ name: body.name })),
      { status: 201 },
    )
  }),
  http.delete('/api/v1/subworkflows/:id/versions/:version', () =>
    HttpResponse.json(voidSuccess()),
  ),
]
