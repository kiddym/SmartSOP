import { http } from './http'
import type { Currency, CurrencyCreate } from '@/types/platform'

// 后端路由前缀 /currencies（见 backend/app/routers/currencies.py）。
export const listCurrencies = () => http.get<Currency[]>('/currencies').then((r) => r.data)

export const createCurrency = (payload: CurrencyCreate) =>
  http.post<Currency>('/currencies', payload).then((r) => r.data)

export const deleteCurrency = (id: string) => http.delete(`/currencies/${id}`).then(() => undefined)
