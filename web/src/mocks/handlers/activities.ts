import { http, HttpResponse } from 'msw'
import type { listActivities } from '@/api/endpoints/activities'
import { emptyPage, paginatedFor } from './helpers'

export const activitiesHandlers = [
  http.get('/api/v1/activities', () =>
    HttpResponse.json(paginatedFor<typeof listActivities>(emptyPage())),
  ),
]
