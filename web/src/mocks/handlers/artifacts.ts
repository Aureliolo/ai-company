import { http, HttpResponse } from 'msw'
import { apiError, apiSuccess } from './helpers'
import type { Artifact, PaginatedResponse, PaginationMeta } from '@/api/types'

const mockArtifacts: Artifact[] = [
  {
    id: 'artifact-abc123',
    type: 'code',
    path: 'src/engine/coordinator.py',
    task_id: 'task-001',
    created_by: 'agent-eng-001',
    description: 'Coordinator implementation',
    project_id: 'proj-001',
    content_type: 'text/plain',
    size_bytes: 4096,
    created_at: '2026-03-30T10:00:00Z',
  },
  {
    id: 'artifact-def456',
    type: 'tests',
    path: 'tests/test_coordinator.py',
    task_id: 'task-001',
    created_by: 'agent-qa-001',
    description: 'Coordinator tests',
    project_id: 'proj-001',
    content_type: 'text/plain',
    size_bytes: 2048,
    created_at: '2026-03-30T11:00:00Z',
  },
  {
    id: 'artifact-ghi789',
    type: 'documentation',
    path: 'docs/coordinator.md',
    task_id: 'task-002',
    created_by: 'agent-eng-001',
    description: 'Coordinator documentation',
    project_id: null,
    content_type: 'text/markdown',
    size_bytes: 1024,
    created_at: '2026-03-30T12:00:00Z',
  },
]

const pagination: PaginationMeta = {
  total: mockArtifacts.length,
  offset: 0,
  limit: 50,
}

export const artifactsList = [
  http.get('/api/v1/artifacts', () => {
    const body: PaginatedResponse<Artifact> = {
      data: mockArtifacts,
      error: null,
      error_detail: null,
      success: true,
      pagination,
    }
    return HttpResponse.json(body)
  }),
  http.get('/api/v1/artifacts/:id', ({ params }) => {
    const artifact = mockArtifacts.find((a) => a.id === params.id)
    if (!artifact) {
      return HttpResponse.json(apiError('Artifact not found'), { status: 404 })
    }
    return HttpResponse.json(apiSuccess(artifact))
  }),
]
