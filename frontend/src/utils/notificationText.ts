import type { RouteLocationRaw } from 'vue-router'
import type { Notification } from '@/types/notification'

/** 通知类型清单(code + 中文 label)。偏好开关、类型过滤共用。
 *  与 backend 的 type 全集一致。 */
export const NOTIFICATION_TYPES: { code: string; label: string }[] = [
  { code: 'WO_ASSIGNED', label: '工单指派' },
  { code: 'WO_STATUS_CHANGED', label: '工单状态变更' },
  { code: 'WO_AUTO_GENERATED', label: '自动生成工单' },
  { code: 'REQUEST_SUBMITTED', label: '新请求提交' },
  { code: 'PO_SUBMITTED', label: '采购单提交' },
  { code: 'PO_APPROVED', label: '采购单审批' },
  { code: 'PM_DUE_SOON', label: '预防性维护即将到期' },
]

function p(n: Notification, key: string): string {
  const v = n.params?.[key]
  return v == null ? '' : String(v)
}

/** 按 type + params 出中文文案(集中处)。未知 type / 缺字段兜底不崩。 */
export function formatNotification(n: Notification): string {
  const cid = p(n, 'custom_id')
  const title = p(n, 'title')
  switch (n.type) {
    case 'WO_ASSIGNED':
      return `工单 ${cid}「${title}」已指派给你`
    case 'WO_STATUS_CHANGED':
      return `工单 ${cid} 状态 ${p(n, 'from_status')} → ${p(n, 'to_status')}`
    case 'WO_AUTO_GENERATED':
      return `自动生成工单 ${cid}「${title}」`
    case 'REQUEST_SUBMITTED':
      return `新请求 ${cid}「${title}」`
    case 'PM_DUE_SOON':
      return `预防性维护 ${cid}「${title}」将于 ${p(n, 'next_due_date')} 到期`
    default:
      if (n.type.startsWith('PO_')) return `采购单 ${cid} 有更新`
      return cid ? `通知 ${cid}` : '你有一条新通知'
  }
}

/** 点击通知的跳转目标;无映射 / 无 entity_id → null(仅标记已读不跳)。 */
export function entityRoute(n: Notification): RouteLocationRaw | null {
  if (!n.entity_id) return null
  if (n.entity_type === 'work_order') {
    return { name: 'maintenance-work-order-detail', params: { id: n.entity_id } }
  }
  if (n.entity_type === 'request') {
    return { path: '/maintenance/requests' }
  }
  return null
}
