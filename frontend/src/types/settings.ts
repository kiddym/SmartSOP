export interface SettingsOut {
  id: string
  enable_approval_workflow: boolean
  max_version_number: number
  require_read_confirmation: boolean
  default_risk_level: number
  default_quality_level: number
  auto_archive_days: number
  enable_version_control: boolean
  revision: number
  created_at: string
  updated_at: string
}

export interface SettingsUpdate {
  enable_approval_workflow?: boolean
  max_version_number?: number
  require_read_confirmation?: boolean
  default_risk_level?: number
  default_quality_level?: number
}
