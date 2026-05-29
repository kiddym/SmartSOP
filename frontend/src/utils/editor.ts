// 编辑器纯函数工具：表单型元数据、警示/富文本类型判定、已废弃字段历史值。

import type { FormType } from '@/types/node'
import type { FieldDetailOut, FieldOption } from '@/types/field'

// ---- 执行表单类型元数据（标签 + 色组，§2.1 类型色条） ---- //

export interface FormTypeMeta {
  label: string
  color: 'gray' | 'blue' | 'purple' | 'cyan' | 'orange' | 'red'
}

export const FORM_TYPE_META: Record<FormType, FormTypeMeta> = {
  COMMON: { label: '通用（操作说明）', color: 'gray' },
  NONE: { label: '无执行记录', color: 'gray' },
  CHECK: { label: '通过/不通过', color: 'blue' },
  YESNO: { label: '是/否', color: 'blue' },
  NUMBER: { label: '数值', color: 'purple' },
  METER: { label: '仪表读数', color: 'purple' },
  CHECKBOX: { label: '多选', color: 'cyan' },
  RADIO: { label: '单选', color: 'cyan' },
  UPLOAD: { label: '文件上传', color: 'orange' },
  PHOTO: { label: '拍照', color: 'orange' },
  SIGNATURE: { label: '签名', color: 'orange' },
  DATE: { label: '日期', color: 'orange' },
  NOTE: { label: '注意', color: 'blue' },
  CAUTION: { label: '小心', color: 'orange' },
  WARNING: { label: '警告', color: 'red' },
}

// 警示类型（渲染成彩色提示框）与富文本类型（用富文本编辑、绑定 content）。
export const ALERT_TYPES: readonly FormType[] = ['NOTE', 'CAUTION', 'WARNING']
export const RICH_TEXT_TYPES: readonly FormType[] = ['COMMON', 'NOTE', 'CAUTION', 'WARNING']
export function isAlertType(t: FormType): boolean {
  return ALERT_TYPES.includes(t)
}
export function isRichTextType(t: FormType): boolean {
  return RICH_TEXT_TYPES.includes(t)
}

// ---- 已废弃自定义字段的历史值（字段归档/删除后值不丢，只读展示，Q255/Q256） ---- //

export interface DeprecatedFieldEntry {
  key: string
  label: string
  value: string
}

type ArchivedFieldDef = Pick<FieldDetailOut, 'key' | 'name' | 'field_type' | 'options'>

function isEmptyCustomValue(v: unknown): boolean {
  return v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)
}

function optionLabel(options: FieldOption[] | undefined, value: unknown): string {
  return options?.find((o) => o.value === value)?.label ?? String(value)
}

function formatDeprecatedValue(raw: unknown, def: ArchivedFieldDef | undefined): string {
  if (Array.isArray(raw)) return raw.map((v) => optionLabel(def?.options, v)).join(', ')
  if (def?.field_type === 'select') return optionLabel(def.options, raw)
  return String(raw)
}

// custom_values 中「仍有非空值、但 key 已不在 active 字段」的条目；标签优先取归档字段名，
// 字段定义彻底删除时回退为 key。
export function collectDeprecatedFieldValues(
  customValues: Record<string, unknown> | null | undefined,
  activeFieldKeys: Iterable<string>,
  archivedFields: ArchivedFieldDef[] = [],
): DeprecatedFieldEntry[] {
  const active = new Set(activeFieldKeys)
  const archived = new Map(archivedFields.map((f) => [f.key, f]))
  const out: DeprecatedFieldEntry[] = []
  for (const [key, raw] of Object.entries(customValues ?? {})) {
    if (active.has(key) || isEmptyCustomValue(raw)) continue
    const def = archived.get(key)
    out.push({ key, label: def?.name ?? key, value: formatDeprecatedValue(raw, def) })
  }
  return out
}

// 树行标题 tooltip 阈值（CJK 字符；30 字之内的 chapter 标题在 240-360px 列宽下基本不省略）
export const TITLE_TOOLTIP_THRESHOLD = 30
