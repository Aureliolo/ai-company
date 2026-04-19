import { http, HttpResponse } from 'msw'
import type {
  grantOrgRole,
  listUsers,
  UserResponse,
} from '@/api/endpoints/users'
import { successFor, voidSuccess } from './helpers'

function buildUser(overrides: Partial<UserResponse> = {}): UserResponse {
  return {
    id: 'user-default',
    username: 'default',
    role: 'ceo',
    must_change_password: false,
    org_roles: [],
    scoped_departments: [],
    created_at: '2026-04-19T00:00:00Z',
    updated_at: '2026-04-19T00:00:00Z',
    ...overrides,
  }
}

export const usersHandlers = [
  http.get('/api/v1/users', () =>
    HttpResponse.json(successFor<typeof listUsers>([])),
  ),
  http.post('/api/v1/users/:id/org-roles', async ({ params, request }) => {
    await request.json()
    return HttpResponse.json(
      successFor<typeof grantOrgRole>(buildUser({ id: String(params.id) })),
    )
  }),
  http.delete('/api/v1/users/:id/org-roles/:role', () =>
    HttpResponse.json(voidSuccess()),
  ),
]
