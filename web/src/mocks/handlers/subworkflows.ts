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
import { buildWorkflow as buildDomainWorkflow } from './workflows'
import { successFor, voidSuccess } from './helpers'

/**
 * Subworkflow-flavoured `buildWorkflow`. Delegates to the canonical
 * workflow builder and just flips `is_subworkflow` true so subworkflow
 * handlers return fixtures that still surface the boundary field that
 * distinguishes them from top-level workflows.
 */
export function buildSubworkflow(
  overrides: Partial<WorkflowDefinition> = {},
): WorkflowDefinition {
  // Spread overrides first, then force is_subworkflow=true so the returned
  // fixture always represents a subworkflow even if the caller accidentally
  // passed `is_subworkflow: false` in the override bag.
  return buildDomainWorkflow({ ...overrides, is_subworkflow: true })
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
        buildSubworkflow({
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
      successFor<typeof createSubworkflow>(buildSubworkflow({ name: body.name })),
      { status: 201 },
    )
  }),
  http.delete('/api/v1/subworkflows/:id/versions/:version', () =>
    HttpResponse.json(voidSuccess()),
  ),
]
