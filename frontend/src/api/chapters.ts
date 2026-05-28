import { http } from './http'
import type { ChapterCreate, ChapterMoveIn, ChapterOut } from '@/types/node'

// 细粒度 action API（编辑器主保存走 PUT /procedures/{id} 整批；本组用于立即移动）。

export const createChapter = async (payload: ChapterCreate): Promise<ChapterOut> =>
  (await http.post<ChapterOut>('/chapters', payload)).data

export const deleteChapter = async (id: string): Promise<void> => {
  await http.delete(`/chapters/${id}`)
}

export const moveChapter = async (id: string, payload: ChapterMoveIn): Promise<ChapterOut> =>
  (await http.post<ChapterOut>(`/chapters/${id}/move`, payload)).data
