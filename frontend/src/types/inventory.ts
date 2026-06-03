// 备件
export interface PartRead {
  id: string
  custom_id: string
  name: string
  description: string
  cost: string
  quantity: string
  min_quantity: string
  unit: string
  barcode: string | null
  non_stock: boolean
  is_low_stock: boolean
  category_id: string | null
  assignee_ids: string[]
  team_ids: string[]
  asset_ids: string[]
  location_ids: string[]
  pm_ids: string[]
}
export interface PartCreate {
  name: string
  description?: string
  cost?: string
  quantity?: string
  min_quantity?: string
  unit?: string
  barcode?: string | null
  non_stock?: boolean
  category_id?: string | null
  assignee_ids?: string[]
  team_ids?: string[]
  asset_ids?: string[]
  location_ids?: string[]
  pm_ids?: string[]
}
export type PartUpdate = Partial<PartCreate>
export interface PartMini {
  id: string
  name: string
  custom_id: string
}

export interface PartCategoryRead {
  id: string
  name: string
  description: string
}
export interface PartCategoryCreate {
  name: string
  description?: string
}
export type PartCategoryUpdate = Partial<PartCategoryCreate>

// 采购单
export type PurchaseOrderStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'CANCELED'

export interface POLineRead {
  id: string
  part_id: string
  quantity: string
  unit_cost: string
  line_total: string
}
export interface POLineCreate {
  part_id: string
  quantity: string
  unit_cost?: string
}

export interface PurchaseOrderRead {
  id: string
  custom_id: string
  vendor_id: string
  status: PurchaseOrderStatus
  notes: string
  category_id: string | null
  shipping_address: string
  shipping_method: string
  terms_of_payment: string
  expected_delivery_date: string | null
  resolution_note: string
  resolved_by_user_id: string | null
  resolved_at: string | null
  lines: POLineRead[]
  total_cost: string
}
export interface PurchaseOrderCreate {
  vendor_id: string
  notes?: string
  category_id?: string | null
  shipping_address?: string
  shipping_method?: string
  terms_of_payment?: string
  expected_delivery_date?: string | null
  lines?: POLineCreate[]
}
export type PurchaseOrderUpdate = Partial<PurchaseOrderCreate>
export interface PurchaseOrderMini {
  id: string
  custom_id: string
  vendor_id: string
  status: PurchaseOrderStatus
}

export interface POActivityRead {
  id: string
  activity_type: string
  actor_user_id: string | null
  from_status: string | null
  to_status: string | null
  comment: string
  created_at: string
}
export interface POResolve {
  note?: string
}

export interface PurchaseOrderCategoryRead {
  id: string
  name: string
  description: string
}
export interface PurchaseOrderCategoryCreate {
  name: string
  description?: string
}
export type PurchaseOrderCategoryUpdate = Partial<PurchaseOrderCategoryCreate>

// 供应商
export interface VendorRead {
  id: string
  name: string
  vendor_type: string
  description: string
  rate: string
  address: string
  phone: string
  email: string
  website: string
  part_ids: string[]
  asset_ids: string[]
  location_ids: string[]
}
export interface VendorCreate {
  name: string
  vendor_type?: string
  description?: string
  rate?: string
  address?: string
  phone?: string
  email?: string
  website?: string
  part_ids?: string[]
  asset_ids?: string[]
  location_ids?: string[]
}
export type VendorUpdate = Partial<VendorCreate>
export interface VendorMini {
  id: string
  name: string
}

// 客户
export interface CustomerRead {
  id: string
  name: string
  customer_type: string
  description: string
  rate: string
  billing_currency: string
  address: string
  phone: string
  email: string
  website: string
  part_ids: string[]
  asset_ids: string[]
  location_ids: string[]
}
export interface CustomerCreate {
  name: string
  customer_type?: string
  description?: string
  rate?: string
  billing_currency?: string
  address?: string
  phone?: string
  email?: string
  website?: string
  part_ids?: string[]
  asset_ids?: string[]
  location_ids?: string[]
}
export type CustomerUpdate = Partial<CustomerCreate>
export interface CustomerMini {
  id: string
  name: string
}
