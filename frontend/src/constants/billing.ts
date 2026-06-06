// 套餐 / 功能码 → 中文展示名。后端目录返回的是 snake_case 英文码（plan/feature），
// 前端统一在此映射成中文，避免在订阅页直接暴露原始英文 key。

export const PLAN_LABELS: Record<string, string> = {
  free: '免费版',
  pro: '专业版',
  enterprise: '企业版',
}

export const FEATURE_LABELS: Record<string, string> = {
  sop: 'SOP 程序管理',
  analytics: '分析仪表盘',
  meters: '计量',
  preventive_maintenance: '预防性维护',
  purchasing: '采购',
}

export const SUBSCRIPTION_STATUS_LABELS: Record<string, string> = {
  active: '生效中',
  trialing: '试用中',
  past_due: '逾期未付',
  canceled: '已取消',
  suspended: '已暂停',
}

/** 未知码兜底返回原码，保证新功能上线前不至于显示空白。 */
export function planLabel(code: string): string {
  return PLAN_LABELS[code] ?? code
}

export function featureLabel(code: string): string {
  return FEATURE_LABELS[code] ?? code
}

export function subscriptionStatusLabel(code: string): string {
  return SUBSCRIPTION_STATUS_LABELS[code] ?? code
}
