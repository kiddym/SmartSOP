import { http } from './http'
import type {
  ChapterCreate,
  ChapterMoveIn,
  ChapterOut,
  ConversionResult,
  MarkStatus,
} from '@/types/node'

// 细粒度 action API（编辑器主保存走 PUT /procedures/{id} 整批；本组用于转换 / 标记 / 立即移动）。

export const createChapter = async (payload: ChapterCreate): Promise<ChapterOut> =>
  (await http.post<ChapterOut>('/chapters', payload)).data

export const deleteChapter = async (id: string): Promise<void> => {
  await http.delete(`/chapters/${id}`)
}

export const moveChapter = async (id: string, payload: ChapterMoveIn): Promise<ChapterOut> =>
  (await http.post<ChapterOut>(`/chapters/${id}/move`, payload)).data

export const setChapterMarkStatus = async (
  id: string,
  markStatus: MarkStatus,
): Promise<ChapterOut> =>
  (await http.post<ChapterOut>(`/chapters/${id}/mark-status`, { mark_status: markStatus })).data

export const convertChapterToStep = async (id: string): Promise<ConversionResult> =>
  (await http.post<ConversionResult>(`/chapters/${id}/convert-to-step`)).data

export const convertRootToStep = async (id: string): Promise<ConversionResult> =>
  (await http.post<ConversionResult>(`/chapters/${id}/convert-root-to-step`)).data

export const convertChapterToContent = async (id: string): Promise<ConversionResult> =>
  (await http.post<ConversionResult>(`/chapters/${id}/convert-to-content`)).data

export const splitChapterTitleContent = async (
  id: string,
  payload: { cursor_offset: number },
): Promise<ConversionResult> =>
  (await http.post<ConversionResult>(`/chapters/${id}/split-title-content`, payload)).data
