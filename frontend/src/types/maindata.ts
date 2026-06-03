export type AssetStatus =
  | 'OPERATIONAL'
  | 'STANDBY'
  | 'MODERNIZATION'
  | 'INSPECTION_SCHEDULED'
  | 'COMMISSIONING'
  | 'EMERGENCY_SHUTDOWN'
  | 'DOWN'

export interface LocationRead {
  id: string
  custom_id: string
  name: string
  description: string
  parent_id: string | null
  address: string
  longitude: number | null
  latitude: number | null
  assigned_user_ids: string[]
  team_ids: string[]
}
export interface LocationCreate {
  name: string
  description?: string
  parent_id?: string | null
  address?: string
  longitude?: number | null
  latitude?: number | null
  assigned_user_ids?: string[]
  team_ids?: string[]
}
export type LocationUpdate = Partial<LocationCreate>
export interface LocationMini {
  id: string
  name: string
  custom_id: string
}

export interface AssetRead {
  id: string
  custom_id: string
  name: string
  description: string
  parent_id: string | null
  location_id: string | null
  category_id: string | null
  status: AssetStatus
  serial_number: string
  model: string
  manufacturer: string
  power: string
  warranty_expiration_date: string | null
  in_service_date: string | null
  acquisition_cost: string | null
  barcode: string | null
  nfc_id: string | null
  primary_user_id: string | null
  assigned_user_ids: string[]
  team_ids: string[]
}
export interface AssetCreate {
  name: string
  description?: string
  parent_id?: string | null
  location_id?: string | null
  category_id?: string | null
  status?: AssetStatus
  serial_number?: string
  model?: string
  manufacturer?: string
  power?: string
  warranty_expiration_date?: string | null
  in_service_date?: string | null
  acquisition_cost?: string | null
  barcode?: string | null
  nfc_id?: string | null
  primary_user_id?: string | null
  assigned_user_ids?: string[]
  team_ids?: string[]
}
export type AssetUpdate = Partial<AssetCreate>
export interface AssetMini {
  id: string
  name: string
  custom_id: string
}

export interface AssetCategoryRead {
  id: string
  name: string
}
export interface AssetCategoryCreate {
  name: string
}
export interface AssetCategoryUpdate {
  name?: string
}

export interface DowntimeRead {
  id: string
  asset_id: string
  started_at: string
  ended_at: string | null
  reason: string
  downtime_type: string
  source_asset_id: string | null
}
export interface DowntimeCreate {
  started_at: string
  ended_at?: string | null
  reason?: string
  downtime_type?: string
}
export interface DowntimeClose {
  ended_at: string
}
