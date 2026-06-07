export type CustomFieldType =
  | 'text' | 'number' | 'date' | 'select' | 'multi_select' | 'checkbox' | 'textarea'
export type CustomFieldEntity = 'work_order' | 'asset' | 'request' | 'location' | 'part'

export interface CustomFieldOption {
  value: string
  label?: string
  archived?: boolean
}
export interface CustomFieldValidation {
  min_length?: number | null
  max_length?: number | null
  pattern?: string | null
  minimum?: number | null
  maximum?: number | null
}
export interface CustomFieldDef {
  id: string
  entity_type: CustomFieldEntity
  key: string
  name: string
  field_type: CustomFieldType
  description: string
  required: boolean
  default_value: unknown | null
  options: CustomFieldOption[]
  validation_rules: Record<string, unknown>
  sort_order: number
  status: string
}
export interface CustomFieldCreate {
  entity_type: CustomFieldEntity
  key: string
  name: string
  field_type: CustomFieldType
  description?: string
  required?: boolean
  default_value?: unknown | null
  options?: CustomFieldOption[]
  validation?: CustomFieldValidation
  sort_order?: number
}
export type CustomFieldUpdate = Omit<CustomFieldCreate, 'entity_type' | 'key' | 'field_type'>
