import { http } from './http'
import type { AuditLogPage, ProcedureAuditLogPage, AuditLogFilter } from '@/types/auditLog'

export async function getFolderAuditLogs(filter: AuditLogFilter): Promise<AuditLogPage> {
  const res = await http.get<AuditLogPage>('/audit-logs/folders', { params: filter })
  return res.data
}

export async function getProcedureAuditLogs(
  filter: AuditLogFilter & { procedure_group_id?: string }
): Promise<ProcedureAuditLogPage> {
  const res = await http.get<ProcedureAuditLogPage>('/audit-logs/procedures', { params: filter })
  return res.data
}

export function exportFolderAuditLogs(filter: Omit<AuditLogFilter, 'page' | 'page_size'>): void {
  const params = new URLSearchParams()
  if (filter.target_id) params.set('target_id', filter.target_id)
  if (filter.action) params.set('action', filter.action)
  if (filter.date_from) params.set('date_from', filter.date_from)
  if (filter.date_to) params.set('date_to', filter.date_to)
  if (filter.ip_address) params.set('ip_address', filter.ip_address)
  params.set('export', 'csv')
  const base = http.defaults.baseURL ?? '/api/v1'
  window.open(`${base}/audit-logs/folders?${params}`)
}

export function exportProcedureAuditLogs(filter: Omit<AuditLogFilter, 'page' | 'page_size'>): void {
  const params = new URLSearchParams()
  if (filter.target_id) params.set('target_id', filter.target_id)
  if (filter.action) params.set('action', filter.action)
  if (filter.date_from) params.set('date_from', filter.date_from)
  if (filter.date_to) params.set('date_to', filter.date_to)
  if (filter.ip_address) params.set('ip_address', filter.ip_address)
  params.set('export', 'csv')
  const base = http.defaults.baseURL ?? '/api/v1'
  window.open(`${base}/audit-logs/procedures?${params}`)
}
