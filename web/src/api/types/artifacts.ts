/** Artifact metadata and filter types. */

import type { ArtifactType } from './enums'

export interface Artifact {
  id: string
  type: ArtifactType
  path: string
  task_id: string
  created_by: string
  description: string
  project_id: string | null
  content_type: string
  size_bytes: number
  created_at: string | null
}

export interface CreateArtifactRequest {
  type: ArtifactType
  path: string
  task_id: string
  created_by: string
  description?: string
  content_type?: string
  project_id?: string | null
}

export interface ArtifactFilters {
  task_id?: string
  created_by?: string
  type?: ArtifactType
  project_id?: string
  offset?: number
  limit?: number
}
