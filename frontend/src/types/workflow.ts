export type WorkflowTrigger = 'WORK_ORDER_CREATED' | 'WORK_ORDER_STATUS_CHANGED'
export type ConditionField = 'status' | 'priority' | 'category_id'
export type ConditionOp = 'eq' | 'ne'
export type ActionType =
  | 'set_priority'
  | 'set_status'
  | 'set_category'
  | 'set_assignee_user'
  | 'set_team'

export interface WorkflowCondition {
  field: ConditionField
  op: ConditionOp
  value: string | null
}

export interface WorkflowAction {
  type: ActionType
  value: string | null
}

export interface WorkflowRead {
  id: string
  name: string
  enabled: boolean
  trigger: WorkflowTrigger
  conditions: WorkflowCondition[]
  actions: WorkflowAction[]
}

export interface WorkflowCreate {
  name: string
  enabled?: boolean
  trigger: WorkflowTrigger
  conditions: WorkflowCondition[]
  actions: WorkflowAction[]
}

export interface WorkflowUpdate {
  name?: string
  enabled?: boolean
  trigger?: WorkflowTrigger
  conditions?: WorkflowCondition[]
  actions?: WorkflowAction[]
}
