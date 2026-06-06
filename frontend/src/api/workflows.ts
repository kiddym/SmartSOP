import { http } from './http'
import type { WorkflowRead, WorkflowCreate, WorkflowUpdate } from '@/types/workflow'

export const listWorkflows = () => http.get<WorkflowRead[]>('/workflows').then((r) => r.data)
export const createWorkflow = (p: WorkflowCreate) =>
  http.post<WorkflowRead>('/workflows', p).then((r) => r.data)
export const updateWorkflow = (id: string, p: WorkflowUpdate) =>
  http.patch<WorkflowRead>(`/workflows/${id}`, p).then((r) => r.data)
export const deleteWorkflow = (id: string) =>
  http.delete(`/workflows/${id}`).then(() => undefined)
