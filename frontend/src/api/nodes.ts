import { http } from './http'
import type { Node, NodeBatchUpdates, NodeCreate, NodePatch } from '@/types/node'

// 统一节点 API 客户端（spec §4）。结构编辑走 batch（返回全量 + 清 review）；
// 内容编辑走 patch（If-Match 乐观锁，返回单节点）；增删/重排后调用方 re-GET。

export const listNodes = async (procedureId: string): Promise<Node[]> =>
  (await http.get<Node[]>(`/procedures/${procedureId}/nodes`)).data

export const patchNode = async (
  nodeId: string,
  patch: NodePatch,
  revision: number,
): Promise<Node> =>
  (
    await http.patch<Node>(`/nodes/${nodeId}`, patch, {
      headers: { 'If-Match': String(revision) },
      skipErrorToast: true, // 冲突/校验错误由 nodeEditor store 自管提示（reload-wins）
    })
  ).data

export const createNode = async (procedureId: string, payload: NodeCreate): Promise<Node> =>
  (await http.post<Node>(`/procedures/${procedureId}/nodes`, payload)).data

export const deleteNode = async (nodeId: string): Promise<void> => {
  await http.delete(`/nodes/${nodeId}`)
}

export const batchUpdateNodes = async (
  procedureId: string,
  updates: NodeBatchUpdates,
): Promise<Node[]> =>
  (await http.patch<Node[]>(`/procedures/${procedureId}/nodes:batch`, { updates })).data

export const reorderNodes = async (
  procedureId: string,
  orderedIds: string[],
): Promise<void> => {
  await http.post(`/procedures/${procedureId}/nodes/reorder`, { ordered_ids: orderedIds })
}
