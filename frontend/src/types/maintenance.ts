import type { AssetStatus } from './maindata'

// 公共
export type WorkOrderPriority = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'

export interface ActivityRead {
  id: string
  activity_type: string
  actor_user_id: string | null
  from_status: string | null
  to_status: string | null
  comment: string
  created_at: string
}
export interface CommentCreate {
  comment: string
}

// 请求
export type RequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELED'

export interface RequestRead {
  id: string
  custom_id: string
  title: string
  description: string
  priority: WorkOrderPriority
  due_date: string | null
  asset_id: string | null
  location_id: string | null
  status: RequestStatus
  work_order_id: string | null
  resolution_note: string
  resolved_by_user_id: string | null
  resolved_at: string | null
}
export interface RequestCreate {
  title: string
  description?: string
  priority?: WorkOrderPriority
  due_date?: string | null
  asset_id?: string | null
  location_id?: string | null
}
export type RequestUpdate = Partial<RequestCreate>
export interface RequestApprove {
  note?: string
  primary_user_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
  procedure_id?: string | null
  // 审批同时联动关联资产状态（可空）：仅当请求关联了资产时由前端附带。
  asset_status?: AssetStatus | null
}
export interface RequestReason {
  reason: string
}

// PM
export type PMFrequencyUnit = 'DAY' | 'WEEK' | 'MONTH'

export interface PMRead {
  id: string
  custom_id: string
  title: string
  description: string
  priority: WorkOrderPriority
  asset_id: string | null
  location_id: string | null
  primary_user_id: string | null
  procedure_id: string | null
  start_date: string
  frequency_unit: PMFrequencyUnit
  frequency_value: number
  due_date_delay: number
  ends_on: string | null
  next_due_date: string
  is_enabled: boolean
  last_generated_at: string | null
  last_work_order_id: string | null
  assignee_ids: string[]
  team_ids: string[]
}
export interface PMCreate {
  title: string
  description?: string
  priority?: WorkOrderPriority
  asset_id?: string | null
  location_id?: string | null
  primary_user_id?: string | null
  procedure_id?: string | null
  start_date: string
  frequency_unit: PMFrequencyUnit
  frequency_value: number
  due_date_delay?: number
  ends_on?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
}
export type PMUpdate = Partial<PMCreate>

// 计量
export type MeterComparator = 'LESS_THAN' | 'MORE_THAN'

export interface MeterRead {
  id: string
  custom_id: string
  name: string
  unit: string
  update_frequency_days: number | null
  asset_id: string | null
  location_id: string | null
  meter_category_id: string | null
  image_url: string | null
  user_ids: string[]
}
export interface MeterCreate {
  name: string
  unit?: string
  update_frequency_days?: number | null
  asset_id?: string | null
  location_id?: string | null
  meter_category_id?: string | null
  image_url?: string | null
  user_ids?: string[] | null
}
export type MeterUpdate = Partial<MeterCreate>

export interface MeterCategoryRead {
  id: string
  name: string
  description: string | null
}
export interface MeterCategoryCreate {
  name: string
  description?: string | null
}
export interface MeterCategoryUpdate {
  name?: string
  description?: string | null
}

export interface MeterReadingRead {
  id: string
  meter_id: string
  value: string
  reading_at: string
  recorded_by_user_id: string | null
}
export interface MeterReadingCreate {
  value: string
  reading_at?: string | null
}
export interface ReadingResult {
  reading: MeterReadingRead
  generated_work_order_ids: string[]
}

export interface TriggerRead {
  id: string
  meter_id: string
  name: string
  comparator: MeterComparator
  threshold: string
  is_armed: boolean
  is_enabled: boolean
  priority: WorkOrderPriority
  title: string
  description: string
  primary_user_id: string | null
  procedure_id: string | null
  last_triggered_at: string | null
  last_work_order_id: string | null
  assignee_ids: string[]
  team_ids: string[]
}
export interface TriggerCreate {
  name: string
  comparator: MeterComparator
  threshold: string
  priority?: WorkOrderPriority
  title: string
  description?: string
  primary_user_id?: string | null
  procedure_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
}
export type TriggerUpdate = Partial<TriggerCreate>

// procedure 下拉
export interface ProcedureMini {
  id: string
  name: string
}
