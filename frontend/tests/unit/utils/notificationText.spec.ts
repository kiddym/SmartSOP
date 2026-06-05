import { describe, it, expect } from 'vitest'
import { formatNotification, entityRoute, NOTIFICATION_TYPES } from '@/utils/notificationText'
import type { Notification } from '@/types/notification'

function n(over: Partial<Notification>): Notification {
  return {
    id: 'x', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
    params: {}, actor_user_id: null, is_read: false, read_at: null,
    created_at: '2026-06-05T00:00:00', ...over,
  }
}

describe('formatNotification', () => {
  it('WO_ASSIGNED 含编码与标题', () => {
    const s = formatNotification(n({ type: 'WO_ASSIGNED', params: { custom_id: 'C-1', title: '巡检' } }))
    expect(s).toContain('C-1')
    expect(s).toContain('巡检')
    expect(s).toContain('指派')
  })
  it('WO_STATUS_CHANGED 含状态迁移', () => {
    const s = formatNotification(n({ type: 'WO_STATUS_CHANGED', params: { custom_id: 'C-2', from_status: 'OPEN', to_status: 'DONE' } }))
    expect(s).toContain('C-2'); expect(s).toContain('OPEN'); expect(s).toContain('DONE')
  })
  it('REQUEST_SUBMITTED 含请求编码', () => {
    const s = formatNotification(n({ type: 'REQUEST_SUBMITTED', entity_type: 'request', params: { custom_id: 'R-1', title: '报修' } }))
    expect(s).toContain('R-1'); expect(s).toContain('报修')
  })
  it('未知 type 兜底不崩', () => {
    expect(formatNotification(n({ type: 'WHATEVER_NEW', params: {} }))).toBeTruthy()
  })
  it('缺 params 字段不抛', () => {
    expect(() => formatNotification(n({ type: 'WO_ASSIGNED', params: {} }))).not.toThrow()
  })
})

describe('entityRoute', () => {
  it('work_order → 详情命名路由', () => {
    expect(entityRoute(n({ entity_type: 'work_order', entity_id: 'wo9' }))).toEqual({
      name: 'maintenance-work-order-detail', params: { id: 'wo9' },
    })
  })
  it('request → 列表路径', () => {
    expect(entityRoute(n({ entity_type: 'request', entity_id: 'r1' }))).toEqual({ path: '/maintenance/requests' })
  })
  it('无 entity_id → null', () => {
    expect(entityRoute(n({ entity_type: 'work_order', entity_id: null }))).toBeNull()
  })
})

describe('NOTIFICATION_TYPES', () => {
  it('含已知类型与中文 label', () => {
    const codes = NOTIFICATION_TYPES.map((t) => t.code)
    expect(codes).toContain('WO_ASSIGNED')
    expect(NOTIFICATION_TYPES.every((t) => typeof t.label === 'string' && t.label.length > 0)).toBe(true)
  })
})
