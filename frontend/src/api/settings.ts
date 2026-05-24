import { http } from './http'
import type { SettingsOut, SettingsUpdate } from '@/types/settings'

export async function getSettings(): Promise<SettingsOut> {
  const res = await http.get<SettingsOut>('/settings/current')
  return res.data
}

export async function updateSettings(data: SettingsUpdate, revision: number): Promise<SettingsOut> {
  const res = await http.put<SettingsOut>('/settings', data, {
    headers: { 'If-Match': String(revision) }
  })
  return res.data
}
