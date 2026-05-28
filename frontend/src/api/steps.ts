import { http } from './http'
import type { StepMoveIn, StepOut } from '@/types/node'

// 步骤细粒度 action API；编辑器主保存走 PUT /procedures/{id} 整批。

export const deleteStep = async (id: string): Promise<void> => {
  await http.delete(`/steps/${id}`)
}

export const moveStep = async (id: string, payload: StepMoveIn): Promise<StepOut> =>
  (await http.post<StepOut>(`/steps/${id}/move`, payload)).data
