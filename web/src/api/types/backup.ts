/** Backup manifest, inventory and restore types. */

export type BackupTrigger = 'scheduled' | 'manual' | 'shutdown' | 'startup' | 'pre_migration'

export type BackupComponent = 'persistence' | 'memory' | 'config'

export interface BackupManifest {
  synthorg_version: string
  timestamp: string
  trigger: BackupTrigger
  readonly components: readonly BackupComponent[]
  size_bytes: number
  checksum: string
  backup_id: string
}

export interface BackupInfo {
  backup_id: string
  timestamp: string
  trigger: BackupTrigger
  readonly components: readonly BackupComponent[]
  size_bytes: number
  compressed: boolean
}

export interface RestoreRequest {
  backup_id: string
  components?: BackupComponent[] | null
  confirm: boolean
}

export interface RestoreResponse {
  manifest: BackupManifest
  readonly restored_components: readonly BackupComponent[]
  safety_backup_id: string
  restart_required: boolean
}
