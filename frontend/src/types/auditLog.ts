export interface AuditLogItem {
  id: string
  target_id: string
  action: string
  old_value: Record<string, unknown>
  new_value: Record<string, unknown>
  reason: string
  ip_address: string
  user_agent: string
  created_at: string
}

export interface ProcedureAuditLogItem extends AuditLogItem {
  procedure_group_id: string | null
}

export interface AuditLogPage {
  total: number
  page: number
  page_size: number
  items: AuditLogItem[]
}

export interface ProcedureAuditLogPage {
  total: number
  page: number
  page_size: number
  items: ProcedureAuditLogItem[]
}

export interface AuditLogFilter {
  target_id?: string
  action?: string
  date_from?: string
  date_to?: string
  ip_address?: string
  page: number
  page_size: number
}
