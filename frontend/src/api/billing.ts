import { http } from './http'

export interface PlanCatalogEntry {
  plan: string
  seat_limit: number | null
  features: string[]
}

export interface Subscription {
  plan: string
  subscription_status: string
  seat_used: number
  seat_limit: number | null
  features: string[]
  catalog: PlanCatalogEntry[]
}

export const getSubscription = () =>
  http.get<Subscription>('/billing/subscription').then((r) => r.data)
