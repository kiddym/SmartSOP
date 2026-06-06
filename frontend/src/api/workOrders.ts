import { http } from './http'
import type {
  WorkOrderRead,
  WorkOrderCreate,
  WorkOrderUpdate,
  WorkOrderStatus,
  WorkOrderPriority,
  WorkOrderTransition,
  AssigneesSet,
  TeamsSet,
  WorkOrderActivityRead,
  WorkOrderCommentCreate,
  ExecutionView,
  StepResultUpdate,
  LaborRead,
  LaborCreate,
  LaborTimerStart,
  LaborUpdate,
  AdditionalCostRead,
  AdditionalCostCreate,
  AdditionalCostUpdate,
  CostSummaryRead,
  CalendarEvent,
} from '@/types/workOrder'

export interface ListWorkOrdersParams {
  status?: WorkOrderStatus
  priority?: WorkOrderPriority
  asset_id?: string
  location_id?: string
  assignee_id?: string
  procedure_attached?: boolean
}

export const listWorkOrders = (params: ListWorkOrdersParams = {}) =>
  http.get<WorkOrderRead[]>('/work-orders', { params }).then((r) => r.data)
export const getWorkOrder = (id: string) =>
  http.get<WorkOrderRead>(`/work-orders/${id}`).then((r) => r.data)
export const listWorkOrderEvents = (start: string, end: string) =>
  http.get<CalendarEvent[]>('/work-orders/events', { params: { start, end } }).then((r) => r.data)
export const createWorkOrder = (p: WorkOrderCreate) =>
  http.post<WorkOrderRead>('/work-orders', p).then((r) => r.data)
export const updateWorkOrder = (id: string, p: WorkOrderUpdate) =>
  http.patch<WorkOrderRead>(`/work-orders/${id}`, p).then((r) => r.data)
export const deleteWorkOrder = (id: string) =>
  http.delete(`/work-orders/${id}`).then(() => undefined)
export const setAssignees = (id: string, p: AssigneesSet) =>
  http.put<WorkOrderRead>(`/work-orders/${id}/assignees`, p).then((r) => r.data)
export const setTeams = (id: string, p: TeamsSet) =>
  http.put<WorkOrderRead>(`/work-orders/${id}/teams`, p).then((r) => r.data)
export const transitionWorkOrder = (id: string, p: WorkOrderTransition) =>
  http.post<WorkOrderRead>(`/work-orders/${id}/transition`, p).then((r) => r.data)
export const attachProcedure = (id: string, p: { procedure_id: string }) =>
  http.post<WorkOrderRead>(`/work-orders/${id}/attach-procedure`, p).then((r) => r.data)
export const detachProcedure = (id: string) =>
  http.delete<WorkOrderRead>(`/work-orders/${id}/procedure`).then((r) => r.data)
export const listWorkOrderActivities = (id: string) =>
  http.get<WorkOrderActivityRead[]>(`/work-orders/${id}/activities`).then((r) => r.data)
export const addWorkOrderComment = (id: string, p: WorkOrderCommentCreate) =>
  http.post<WorkOrderActivityRead>(`/work-orders/${id}/activities`, p).then((r) => r.data)
export const getExecution = (id: string) =>
  http.get<ExecutionView>(`/work-orders/${id}/execution`).then((r) => r.data)
/** 写入单个执行步骤（response/is_done/notes），返回刷新后的整张执行视图。 */
export const patchStepResult = (id: string, resultId: string, p: StepResultUpdate) =>
  http.patch<ExecutionView>(`/work-orders/${id}/steps/${resultId}`, p).then((r) => r.data)

export const listLabor = (id: string) =>
  http.get<LaborRead[]>(`/work-orders/${id}/labor`).then((r) => r.data)
export const createLabor = (id: string, p: LaborCreate) =>
  http.post<LaborRead>(`/work-orders/${id}/labor`, p).then((r) => r.data)
export const startTimer = (id: string, p: LaborTimerStart = {}) =>
  http.post<LaborRead>(`/work-orders/${id}/labor/start`, p).then((r) => r.data)
export const stopTimer = (id: string, laborId: string) =>
  http.post<LaborRead>(`/work-orders/${id}/labor/${laborId}/stop`).then((r) => r.data)
export const updateLabor = (id: string, laborId: string, p: LaborUpdate) =>
  http.patch<LaborRead>(`/work-orders/${id}/labor/${laborId}`, p).then((r) => r.data)
export const deleteLabor = (id: string, laborId: string) =>
  http.delete(`/work-orders/${id}/labor/${laborId}`).then(() => undefined)

export const listAdditionalCosts = (id: string) =>
  http.get<AdditionalCostRead[]>(`/work-orders/${id}/additional-costs`).then((r) => r.data)
export const createAdditionalCost = (id: string, p: AdditionalCostCreate) =>
  http.post<AdditionalCostRead>(`/work-orders/${id}/additional-costs`, p).then((r) => r.data)
export const updateAdditionalCost = (id: string, costId: string, p: AdditionalCostUpdate) =>
  http
    .patch<AdditionalCostRead>(`/work-orders/${id}/additional-costs/${costId}`, p)
    .then((r) => r.data)
export const deleteAdditionalCost = (id: string, costId: string) =>
  http.delete(`/work-orders/${id}/additional-costs/${costId}`).then(() => undefined)
export const getCostSummary = (id: string) =>
  http.get<CostSummaryRead>(`/work-orders/${id}/cost-summary`).then((r) => r.data)

/** 拉取工单 PDF 报告（blob，带 Bearer 鉴权）并在浏览器触发下载。 */
export const downloadWorkOrderReport = async (id: string, customId: string) => {
  const res = await http.get(`/work-orders/${id}/report`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `WO-${customId}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
