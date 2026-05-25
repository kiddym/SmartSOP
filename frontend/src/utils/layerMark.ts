export type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content'

/** 文档序里参与层级标定的章节/正文行（步骤不参与）。 */
export interface LayerRow {
  id: string
  content_type: 'chapter' | 'content'
  level: number // 当前层级（预填默认角色用）
  hasStepChildren: boolean // 含步骤子节点 → 不可降为正文
}

/** 应用层级后单个节点的目标归属。 */
export interface LayerUpdate {
  parent_id: string | null
  content_type: 'chapter' | 'content'
  sort_order: number
}

/** 当前角色：content→content；章节按 level 夹到 chapter_1/2/3。 */
export function defaultLayerRole(contentType: 'chapter' | 'content', level: number): LayerRole {
  if (contentType === 'content') return 'content'
  const lv = Math.min(3, Math.max(1, level))
  return `chapter_${lv}` as LayerRole
}

function roleLevel(role: LayerRole): number {
  return role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
}

// 含步骤子节点的行即便被标 content 也保持章节（content 不能有步骤子，Q25）。
function effectiveRole(row: LayerRow, roleMap: Map<string, LayerRole>): LayerRole {
  const role = roleMap.get(row.id) ?? defaultLayerRole(row.content_type, row.level)
  if (role === 'content' && row.hasStepChildren) return defaultLayerRole('chapter', row.level)
  return role
}

/**
 * 由文档序行 + roleMap 算每个章节/正文节点的目标 {parent_id, content_type, sort_order}。
 * l1/l2/l3 走位：chapter_2 无一级父→根；chapter_3 无二级父→挂一级/根；正文挂最近章节、作叶子。
 */
export function computeLayerUpdates(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, LayerUpdate> {
  const out = new Map<string, LayerUpdate>()
  let l1: string | null = null
  let l2: string | null = null
  let l3: string | null = null
  const sortCounter = new Map<string | null, number>()
  const nextSort = (p: string | null): number => {
    const n = sortCounter.get(p) ?? 0
    sortCounter.set(p, n + 1)
    return n
  }
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (role === 'content') {
      const parent = l3 ?? l2 ?? l1
      out.set(row.id, { parent_id: parent, content_type: 'content', sort_order: nextSort(parent) })
      continue
    }
    const level = roleLevel(role)
    let parent: string | null
    if (level >= 3 && l2) {
      parent = l2
      l3 = row.id
    } else if (level >= 2 && l1) {
      parent = l1
      l2 = row.id
      l3 = null
    } else {
      parent = null
      l1 = row.id
      l2 = null
      l3 = null
    }
    out.set(row.id, { parent_id: parent, content_type: 'chapter', sort_order: nextSort(parent) })
  }
  return out
}

/** 「所见即所选」缩进：章节 = level-1；正文 = 当前标题层级。 */
export function computeLayerIndents(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, number> {
  const map = new Map<string, number>()
  let headingLevel = 0
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (role === 'content') {
      map.set(row.id, headingLevel)
    } else {
      const lv = roleLevel(role)
      map.set(row.id, lv - 1)
      headingLevel = lv
    }
  }
  return map
}
