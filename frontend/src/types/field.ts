export type FieldType = 'text' | 'number' | 'date' | 'select' | 'multi_select' | 'checkbox' | 'textarea'
export type FieldStatus = 'active' | 'archived'

export interface FieldOption {
  value: string
  label: string
  archived?: boolean
}

export interface FieldDetailOut {
  id: string
  name: string
  key: string
  field_type: FieldType
  description: string
  required: boolean
  default_value: unknown
  options: FieldOption[]
  validation_rules: Record<string, unknown>
  sort_order: number
  show_on_cover: boolean
  status: FieldStatus
  created_at: string
  updated_at: string
}

export interface FieldCreate {
  name: string
  key: string
  field_type: FieldType
  description?: string
  required?: boolean
  options?: FieldOption[]
  sort_order?: number
  show_on_cover?: boolean
}

export interface FieldUpdate {
  name: string
  description?: string
  required?: boolean
  options?: FieldOption[]
  sort_order?: number
  show_on_cover?: boolean
}
