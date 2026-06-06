// 表单字段配置（FieldConfiguration）：按 form_key 控制某表单各字段的显示/必填。
export interface FieldConfigRead {
  field_name: string
  visible: boolean
  required: boolean
  sort_order: number
}

export interface FieldConfigItem {
  field_name: string
  visible: boolean
  required: boolean
}
