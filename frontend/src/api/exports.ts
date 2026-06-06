import { http } from './http'

export type ExportEntity = 'work-orders' | 'assets' | 'locations' | 'parts' | 'meters'

/** 拉取实体整表 CSV（blob，带 Bearer 鉴权）并在浏览器触发下载。 */
export const exportEntityCsv = async (entity: ExportEntity) => {
  const res = await http.get(`/exports/${entity}`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${entity}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const exportWorkOrders = () => exportEntityCsv('work-orders')
export const exportAssets = () => exportEntityCsv('assets')
export const exportLocations = () => exportEntityCsv('locations')
export const exportParts = () => exportEntityCsv('parts')
export const exportMeters = () => exportEntityCsv('meters')
