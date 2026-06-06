import { http } from './http'
import type { FloorPlanRead, FloorPlanCreate, FloorPlanUpdate } from '@/types/maindata'

const base = (locationId: string) => `/locations/${locationId}/floor-plans`

export const listFloorPlans = (locationId: string) =>
  http.get<FloorPlanRead[]>(base(locationId)).then((r) => r.data)
export const createFloorPlan = (locationId: string, p: FloorPlanCreate) =>
  http.post<FloorPlanRead>(base(locationId), p).then((r) => r.data)
export const updateFloorPlan = (locationId: string, floorPlanId: string, p: FloorPlanUpdate) =>
  http.patch<FloorPlanRead>(`${base(locationId)}/${floorPlanId}`, p).then((r) => r.data)
export const deleteFloorPlan = (locationId: string, floorPlanId: string) =>
  http.delete(`${base(locationId)}/${floorPlanId}`).then(() => undefined)
