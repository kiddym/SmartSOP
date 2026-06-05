import { http } from './http'
import type { PageResult } from '@/types/common'
import type {
  Notification,
  NotificationPreference,
  ListNotificationsParams,
} from '@/types/notification'

export const listNotifications = (params: ListNotificationsParams = {}) =>
  http.get<PageResult<Notification>>('/notifications', { params }).then((r) => r.data)

export const getUnreadCount = () =>
  http.get<{ count: number }>('/notifications/unread-count').then((r) => r.data)

export const markRead = (id: string) =>
  http.post<Notification>(`/notifications/${id}/read`, {}).then((r) => r.data)

export const markAllRead = () =>
  http.post<{ updated: number }>('/notifications/read-all', {}).then((r) => r.data)

export const getPreference = () =>
  http.get<NotificationPreference>('/notification-preferences').then((r) => r.data)

export const putPreference = (p: NotificationPreference) =>
  http.put<NotificationPreference>('/notification-preferences', p).then((r) => r.data)
