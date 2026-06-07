export type WorkOrderStatus = 'OPEN' | 'IN_PROGRESS' | 'ON_HOLD' | 'COMPLETE' | 'CANCELED'
import type { WorkOrderPriority } from './maintenance'
export type { WorkOrderPriority }

export interface WorkOrderRead {
  id: string
  custom_id: string
  title: string
  description: string
  status: WorkOrderStatus
  priority: WorkOrderPriority
  due_date: string | null
  asset_id: string | null
  location_id: string | null
  primary_user_id: string | null
  procedure_id: string | null
  procedure_group_id: string | null
  completed_at: string | null
  category_id: string | null
  created_by_user_id: string | null
  signature_url: string | null
  required_signature: boolean
  assignee_ids: string[]
  team_ids: string[]
  custom_values: Record<string, unknown>
}
export interface WorkOrderCreate {
  title: string
  description?: string
  priority?: WorkOrderPriority
  due_date?: string | null
  asset_id?: string | null
  location_id?: string | null
  primary_user_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
  category_id?: string | null
  procedure_id?: string | null
  required_signature?: boolean
  custom_values?: Record<string, unknown>
}
export interface WorkOrderUpdate {
  title?: string
  description?: string
  priority?: WorkOrderPriority
  due_date?: string | null
  asset_id?: string | null
  location_id?: string | null
  primary_user_id?: string | null
  category_id?: string | null
  required_signature?: boolean
  custom_values?: Record<string, unknown>
}
export interface WorkOrderTransition {
  to_status: WorkOrderStatus
  note?: string
  signature_url?: string | null
}
export interface AssigneesSet {
  user_ids: string[]
}
export interface TeamsSet {
  team_ids: string[]
}

export interface WorkOrderActivityRead {
  id: string
  activity_type: string
  actor_user_id: string | null
  from_status: string | null
  to_status: string | null
  comment: string
  created_at: string
}
export interface WorkOrderCommentCreate {
  comment: string
}

export type CalendarEventType = 'work_order' | 'pm'
export interface CalendarEvent {
  type: CalendarEventType
  id: string
  custom_id: string | null
  title: string
  date: string
  status: WorkOrderStatus | null
  priority: WorkOrderPriority | null
}

export interface TimeCategoryRead {
  id: string
  name: string
  hourly_rate: string
  description: string
}
export interface TimeCategoryCreate {
  name: string
  hourly_rate: string
  description?: string
}
export type TimeCategoryUpdate = Partial<TimeCategoryCreate>

export interface CostCategoryRead {
  id: string
  name: string
  description: string
}
export interface CostCategoryCreate {
  name: string
  description?: string
}
export type CostCategoryUpdate = Partial<CostCategoryCreate>

export interface LaborRead {
  id: string
  work_order_id: string
  user_id: string | null
  time_category_id: string | null
  started_at: string | null
  stopped_at: string | null
  duration_seconds: number
  hourly_rate: string
  notes: string
  include_to_total: boolean
  running: boolean
  cost: string
  running_elapsed_seconds: number | null
}
export interface LaborCreate {
  duration_seconds: number
  time_category_id?: string | null
  hourly_rate?: string | null
  user_id?: string | null
  started_at?: string | null
  stopped_at?: string | null
  notes?: string
  include_to_total?: boolean
}
export interface LaborTimerStart {
  time_category_id?: string | null
  hourly_rate?: string | null
  user_id?: string | null
  notes?: string
}
export interface LaborUpdate {
  duration_seconds?: number
  time_category_id?: string | null
  hourly_rate?: string | null
  user_id?: string | null
  notes?: string
  include_to_total?: boolean
}

export interface AdditionalCostRead {
  id: string
  work_order_id: string
  cost_category_id: string | null
  title: string
  amount: string
  description: string
  created_by_user_id: string | null
  include_to_total: boolean
}
export interface AdditionalCostCreate {
  title: string
  amount: string
  cost_category_id?: string | null
  description?: string
  include_to_total?: boolean
}
export interface AdditionalCostUpdate {
  title?: string
  amount?: string
  cost_category_id?: string | null
  description?: string
  include_to_total?: boolean
}

export interface CostSummaryRead {
  labor_total: string
  additional_total: string
  parts_total: string
  total: string
}

export interface OutlineNode {
  node_id: string
  heading_level: number | null
  kind: string
  body: string
  code: string
  sort_order: number
}
export interface StepResultRead {
  id: string
  node_id: string
  node_code: string
  node_sort_order: number
  input_schema: Record<string, unknown>
  response: Record<string, unknown>
  is_done: boolean
  done_by_user_id: string | null
  done_at: string | null
  notes: string
}
export interface ProcedureRef {
  id: string
  group_id: string | null
  code: string
  name: string
  version: number
}
export interface ExecutionView {
  procedure: ProcedureRef | null
  outline: OutlineNode[]
  steps: StepResultRead[]
}

/** PATCH /work-orders/{id}/steps/{result_id} 入参；字段全可选（部分更新）。 */
export interface StepResultUpdate {
  response?: Record<string, unknown>
  is_done?: boolean
  notes?: string
}

export interface WorkOrderCategoryRead {
  id: string
  name: string
  description: string
}
export interface WorkOrderCategoryCreate {
  name: string
  description?: string
}
export type WorkOrderCategoryUpdate = Partial<WorkOrderCategoryCreate>
