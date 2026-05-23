// 导入向导 sessionStorage 持久化（Q353）。
// 单一全局键（向导无 procedure id）；不持久化 File（不可序列化，upload_token 已足够断点续解析）。
// created_at 超 24h（与临时上传 TTL 一致）→ 静默清除，避免恢复到已被 scheduler 清掉的 token。

import type { ParseMode, ParseResponse } from '@/types/parse'
import type { MarkedImportBlock } from '@/utils/importBlocks'
import type { WizardNode } from '@/utils/importTree'

export const WIZARD_KEY = 'procedure_import_wizard_v2'
export const WIZARD_TTL_MS = 24 * 60 * 60 * 1000

export interface WizardSnapshot {
  created_at: string
  step: number
  upload_token: string
  filename: string
  parse_mode: ParseMode
  parse_result: ParseResponse | null
  tree: WizardNode[]
  marked_blocks: MarkedImportBlock[]
  form: { name: string; folder_id: string }
}

export function saveWizard(snapshot: WizardSnapshot): void {
  try {
    sessionStorage.setItem(WIZARD_KEY, JSON.stringify(snapshot))
  } catch {
    /* 配额满 / 隐私模式：忽略，持久化是尽力而为 */
  }
}

export function clearWizard(): void {
  sessionStorage.removeItem(WIZARD_KEY)
}

export function loadWizard(now: number = Date.now()): WizardSnapshot | null {
  const raw = sessionStorage.getItem(WIZARD_KEY)
  if (!raw) return null
  let snap: WizardSnapshot
  try {
    snap = JSON.parse(raw) as WizardSnapshot
  } catch {
    clearWizard()
    return null
  }
  const created = Date.parse(snap.created_at)
  if (!Number.isFinite(created) || now - created > WIZARD_TTL_MS) {
    clearWizard()
    return null
  }
  return snap
}
