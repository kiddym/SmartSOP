interface ReviewRow {
  id: string
  mark_status: string
}

/**
 * 文档序里 currentId 之后的下一个 review 行 id（环绕）；当前非 review / 无选中时取其后第一个 review。
 * 无 review → null。
 */
export function nextReviewId(rows: ReviewRow[], currentId: string | null): string | null {
  const reviews = rows.filter((r) => r.mark_status === 'review')
  if (reviews.length === 0) return null
  if (currentId === null) return reviews[0].id
  const curIdx = rows.findIndex((r) => r.id === currentId)
  if (curIdx === -1) return reviews[0].id
  for (let i = 1; i <= rows.length; i++) {
    const r = rows[(curIdx + i) % rows.length]
    if (r.mark_status === 'review') return r.id
  }
  return reviews[0].id
}
