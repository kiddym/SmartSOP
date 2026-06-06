// 资产折旧（与资产 1:1）。GET 取（无则 null）/ PUT upsert / DELETE。
// current_value 为后端直线法计算的只读字段。

export interface DeprecationRead {
  id: string
  asset_id: string
  purchase_price: string | null
  purchase_date: string | null
  residual_value: string | null
  useful_life_years: number | null
  rate: string | null
  current_value: string | null
}

export interface DeprecationUpdate {
  purchase_price?: string | null
  purchase_date?: string | null
  residual_value?: string | null
  useful_life_years?: number | null
  rate?: string | null
}
