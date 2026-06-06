import { http } from './http'

export type ImportEntity = 'assets' | 'locations' | 'parts' | 'meters'

export interface ImportRowError {
  row: number
  message: string
}

export interface ImportResult {
  created: number
  failed: number
  errors: ImportRowError[]
}

/** 下载某实体的导入模板 CSV（blob，带 Bearer 鉴权）并在浏览器触发下载。 */
export const downloadTemplate = async (entity: ImportEntity) => {
  const res = await http.get(`/imports/${entity}/template`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${entity}-template.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** 上传 CSV 文件批量导入某实体，返回创建/失败汇总与逐行错误。 */
export const importCsv = async (entity: ImportEntity, file: File): Promise<ImportResult> => {
  const form = new FormData()
  form.append('file', file)
  // 显式清掉默认 application/json，让浏览器自动带 multipart boundary。
  const res = await http.post(`/imports/${entity}`, form, {
    headers: { 'Content-Type': undefined },
  })
  return res.data as ImportResult
}
