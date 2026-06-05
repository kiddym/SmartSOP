export interface Notification {
  id: string
  type: string
  entity_type: string | null
  entity_id: string | null
  params: Record<string, unknown>
  actor_user_id: string | null
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface NotificationPreference {
  email_enabled: boolean
  disabled_types: string[]
}

export interface ListNotificationsParams {
  page?: number
  page_size?: number
  is_read?: boolean
  type?: string
}
