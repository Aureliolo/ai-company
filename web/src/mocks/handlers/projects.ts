import { http, HttpResponse } from 'msw'
import { apiError, apiSuccess } from './helpers'
import type { PaginatedResponse, PaginationMeta, Project } from '@/api/types'

const mockProjects: Project[] = [
  {
    id: 'proj-abc123',
    name: 'Engine Rewrite',
    description: 'Rewrite the coordination engine for v2',
    team: ['agent-eng-001', 'agent-eng-002', 'agent-qa-001'],
    lead: 'agent-eng-001',
    task_ids: ['task-001', 'task-002', 'task-003'],
    deadline: '2026-06-01T00:00:00Z',
    budget: 1500,
    status: 'active',
  },
  {
    id: 'proj-def456',
    name: 'Documentation Sprint',
    description: 'Update all user-facing documentation',
    team: ['agent-eng-003'],
    lead: 'agent-eng-003',
    task_ids: ['task-004'],
    deadline: null,
    budget: 200,
    status: 'planning',
  },
]

const pagination: PaginationMeta = {
  total: mockProjects.length,
  offset: 0,
  limit: 50,
}

export const projectsList = [
  http.get('/api/v1/projects', () => {
    const body: PaginatedResponse<Project> = {
      data: mockProjects,
      error: null,
      error_detail: null,
      success: true,
      pagination,
    }
    return HttpResponse.json(body)
  }),
  http.get('/api/v1/projects/:id', ({ params }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) {
      return HttpResponse.json(apiError('Project not found'), { status: 404 })
    }
    return HttpResponse.json(apiSuccess(project))
  }),
]
