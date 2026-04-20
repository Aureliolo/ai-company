/** Enum types and their runtime VALUES arrays shared across the dashboard. */

export type TaskStatus =
  | 'created'
  | 'assigned'
  | 'in_progress'
  | 'in_review'
  | 'completed'
  | 'blocked'
  | 'failed'
  | 'interrupted'
  | 'suspended'
  | 'cancelled'
  | 'rejected'
  | 'auth_required'

export type TaskType =
  | 'development'
  | 'design'
  | 'research'
  | 'review'
  | 'meeting'
  | 'admin'

export type TaskSource = 'internal' | 'client' | 'simulation'

export type Priority = 'critical' | 'high' | 'medium' | 'low'

export type Complexity = 'simple' | 'medium' | 'complex' | 'epic'

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export type ApprovalRiskLevel = 'low' | 'medium' | 'high' | 'critical'

export type UrgencyLevel = 'critical' | 'high' | 'normal' | 'no_expiry'

export type SeniorityLevel =
  | 'junior'
  | 'mid'
  | 'senior'
  | 'lead'
  | 'principal'
  | 'director'
  | 'vp'
  | 'c_suite'

export type AgentStatus = 'active' | 'onboarding' | 'on_leave' | 'terminated'

export const SENIORITY_LEVEL_VALUES = [
  'junior', 'mid', 'senior', 'lead', 'principal', 'director', 'vp', 'c_suite',
] as const satisfies readonly SeniorityLevel[]

export const AGENT_STATUS_VALUES = [
  'active', 'onboarding', 'on_leave', 'terminated',
] as const satisfies readonly AgentStatus[]

export type AutonomyLevel = 'full' | 'semi' | 'supervised' | 'locked'

export type OrgRole = 'owner' | 'department_admin' | 'editor' | 'viewer'

export type HumanRole =
  | 'ceo'
  | 'manager'
  | 'board_member'
  | 'pair_programmer'
  | 'observer'
  | 'system'

export type DepartmentName =
  | 'executive'
  | 'product'
  | 'design'
  | 'engineering'
  | 'quality_assurance'
  | 'data_analytics'
  | 'operations'
  | 'creative_marketing'
  | 'security'

export const DEPARTMENT_NAME_VALUES = [
  'executive', 'product', 'design', 'engineering', 'quality_assurance',
  'data_analytics', 'operations', 'creative_marketing', 'security',
] as const satisfies readonly DepartmentName[]

export type ProjectStatus =
  | 'planning'
  | 'active'
  | 'on_hold'
  | 'completed'
  | 'cancelled'

export const PROJECT_STATUS_VALUES = [
  'planning', 'active', 'on_hold', 'completed', 'cancelled',
] as const satisfies readonly ProjectStatus[]

export type ArtifactType = 'code' | 'tests' | 'documentation'

export const ARTIFACT_TYPE_VALUES = [
  'code', 'tests', 'documentation',
] as const satisfies readonly ArtifactType[]

export type RiskTolerance = 'low' | 'medium' | 'high'

export type CreativityLevel = 'low' | 'medium' | 'high'

export type DecisionMakingStyle = 'analytical' | 'intuitive' | 'consultative' | 'directive'

export type CollaborationPreference = 'independent' | 'pair' | 'team'

export type CommunicationVerbosity = 'terse' | 'balanced' | 'verbose'

export type ConflictApproach = 'avoid' | 'accommodate' | 'compete' | 'compromise' | 'collaborate'

export type TaskStructure = 'sequential' | 'parallel' | 'mixed'

export type CoordinationTopology = 'sas' | 'centralized' | 'decentralized' | 'context_dependent' | 'auto'

export type ToolAccessLevel = 'sandboxed' | 'restricted' | 'standard' | 'elevated' | 'custom'

export type MemoryLevel = 'persistent' | 'project' | 'session' | 'none'
