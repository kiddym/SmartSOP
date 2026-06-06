import { http } from './http'
import type { FieldConfigRead, FieldConfigItem } from '@/types/fieldConfig'

// 表单字段配置：GET 任意认证用户可读；PUT 需 company.settings 权限。
export const getFieldConfig = (formKey: string) =>
  http.get<FieldConfigRead[]>(`/field-configurations/${formKey}`).then((r) => r.data)

export const putFieldConfig = (formKey: string, items: FieldConfigItem[]) =>
  http.put<FieldConfigRead[]>(`/field-configurations/${formKey}`, items).then((r) => r.data)
