// 动态标题字典-编号体例 API（方案 M4b）。
import { http } from './http'

export interface NumberingProfile {
  id: string
  pattern_key: string
  kind: string // 'heading' | 'weak_heading' | 'list'
  level: number | null
  source: string
  status: string
  level_votes: Record<string, number>
  evidence_count: number
  agreement: number
  revision: number
  created_at: string
  updated_at: string
}

export const listNumberingProfiles = async (): Promise<NumberingProfile[]> =>
  (await http.get<NumberingProfile[]>('/numbering-profiles')).data

export const createNumberingProfile = async (
  patternKey: string,
  kind: string,
  level: number | null,
): Promise<NumberingProfile> =>
  (
    await http.post<NumberingProfile>('/numbering-profiles', {
      pattern_key: patternKey,
      kind,
      level,
    })
  ).data

export const updateNumberingProfile = async (
  id: string,
  patch: { kind?: string; level?: number | null; status?: string },
): Promise<NumberingProfile> =>
  (await http.put<NumberingProfile>(`/numbering-profiles/${id}`, patch)).data

export const deleteNumberingProfile = async (id: string): Promise<void> => {
  await http.delete(`/numbering-profiles/${id}`)
}
