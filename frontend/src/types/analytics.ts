export interface AnalyticsParams {
  date_from?: string
  date_to?: string
  asset_id?: string
  location_id?: string
  category_id?: string
  granularity?: 'day' | 'week'
}

export interface CountRow {
  asset_id: string | null
  user_id: string | null
  category_id: string | null
  count: number
}

export interface WorkOrderAnalytics {
  date_from: string
  date_to: string
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  completed: number
  completion_rate: number
  overdue: number
  avg_cycle_time_hours: number | null
  avg_response_time_hours: number | null
  by_asset: CountRow[]
  by_user: CountRow[]
  by_category: CountRow[]
}

export interface RequestAnalytics {
  date_from: string
  date_to: string
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  received: number
  resolved: number
  converted: number
  avg_resolution_cycle_hours: number | null
}

export interface PartCostRow {
  part_id: string
  custom_id: string
  name: string
  qty: string
  cost: string
}
export interface AssetCostRow {
  asset_id: string | null
  cost: string
}
export interface VendorSpendRow {
  vendor_id: string
  spend: string
}
export interface MaintenanceCostByAssetRow {
  asset_id: string | null
  parts_cost: string
  labor_cost: string
  additional_cost: string
  total: string
}
export interface CostAnalytics {
  date_from: string
  date_to: string
  parts_consumption_cost: string
  consumption_by_part: PartCostRow[]
  consumption_by_asset: AssetCostRow[]
  po_spend_approved: string
  po_spend_by_vendor: VendorSpendRow[]
  labor_cost: string
  additional_cost: string
  total_maintenance_cost: string
  maintenance_cost_by_asset: MaintenanceCostByAssetRow[]
}

export interface AssetReliabilityRow {
  asset_id: string
  custom_id: string
  name: string
  availability_pct: number
  downtime_count: number
  total_downtime_hours: number
  mttr_hours: number | null
  mtbf_hours: number | null
  total_maintenance_cost: string
  acquisition_cost: string | null
  cost_to_value_ratio: number | null
}
export interface AssetReliabilityAnalytics {
  date_from: string
  date_to: string
  window_hours: number
  assets: AssetReliabilityRow[]
  fleet_availability_pct: number | null
  fleet_total_downtime_hours: number
  fleet_mttr_hours: number | null
  fleet_mtbf_hours: number | null
  fleet_total_maintenance_cost: string
}

export interface CategoryValueRow {
  category_id: string | null
  name: string | null
  value: string
}
export interface LowStockRow {
  part_id: string
  custom_id: string
  name: string
  quantity: string
  min_quantity: string
  shortfall: string
}
export interface TopConsumedRow {
  part_id: string
  custom_id: string
  name: string
  qty: string
}
export interface ABCRow {
  part_id: string
  custom_id: string
  name: string
  consumption_value: string
  cumulative_pct: number
  abc_class: string
}
export interface InventoryAnalytics {
  total_inventory_value: string
  inventory_value_by_category: CategoryValueRow[]
  low_stock_count: number
  low_stock_items: LowStockRow[]
  top_consumed_parts: TopConsumedRow[]
  abc_classification: ABCRow[]
  abc_summary: Record<string, number>
}

export interface PersonnelRow {
  user_id: string
  name: string | null
  created_count: number
  completed_count: number
  assigned_count: number
  labor_hours: number
  labor_cost: string
}
export interface PersonnelAnalytics {
  date_from: string
  date_to: string
  users: PersonnelRow[]
}

export interface TrendBucket {
  bucket_start: string
  work_orders_created: number
  work_orders_completed: number
  requests_received: number
  requests_resolved: number
}
export interface TrendAnalytics {
  date_from: string
  date_to: string
  granularity: string
  buckets: TrendBucket[]
}
