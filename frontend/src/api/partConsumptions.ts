import { http } from './http'
import type { PartConsumptionRead, PartConsumptionCreate } from '@/types/inventory'

export const listPartConsumptions = (workOrderId: string) =>
  http
    .get<PartConsumptionRead[]>(`/work-orders/${workOrderId}/part-consumptions`)
    .then((r) => r.data)

export const consumePart = (workOrderId: string, payload: PartConsumptionCreate) =>
  http
    .post<PartConsumptionRead>(`/work-orders/${workOrderId}/part-consumptions`, payload)
    .then((r) => r.data)
