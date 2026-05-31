// 动态标题字典-样式规则 API（动态标题字典与自学习方案 M1/M2）。
import { http } from './http'

export interface HeadingRule {
  id: string
  style_name: string
  level: number | null
  source: string // 'manual' | 'learned' | 'disabled'
  status: string // 'active' | 'candidate'
  level_votes: Record<string, number>
  evidence_count: number
  agreement: number
  revision: number
  created_at: string
  updated_at: string
}

export const listHeadingRules = async (): Promise<HeadingRule[]> =>
  (await http.get<HeadingRule[]>('/heading-rules')).data

// 记住此样式：写入 manual 规则（即时 active），下次同样式免确认。
export const createHeadingRule = async (
  styleName: string,
  level: number | null,
): Promise<HeadingRule> =>
  (await http.post<HeadingRule>('/heading-rules', { style_name: styleName, level })).data

export const updateHeadingRule = async (
  id: string,
  patch: { level?: number | null; status?: string },
): Promise<HeadingRule> => (await http.put<HeadingRule>(`/heading-rules/${id}`, patch)).data

export const deleteHeadingRule = async (id: string): Promise<void> => {
  await http.delete(`/heading-rules/${id}`)
}
