import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'

import * as api from '@/api/batchImports'
import { isVersionConflict } from '@/api/http'
import type {
  ApplyPreview, BatchBlob, BatchImportItem, BatchImportJob, ReviewOp,
} from '@/types/batchImport'

const TIER_RANK: Record<string, number> = { failed: 0, low: 1, medium: 2, high: 3 }

interface State {
  jobId: string | null
  job: BatchImportJob | null
  items: BatchImportItem[]
  statusFilter: string | null
  currentItemId: string | null
  blob: BatchBlob | null
  reviewRevision: number
  loading: boolean
  polling: number | null
}

function rank(item: BatchImportItem): number {
  if (item.status === 'failed') return -1
  return TIER_RANK[item.summary.confidence_tier ?? 'high'] ?? 3
}

export const useBatchReviewStore = defineStore('batchReview', {
  state: (): State => ({
    jobId: null, job: null, items: [], statusFilter: null,
    currentItemId: null, blob: null, reviewRevision: 1, loading: false, polling: null,
  }),

  getters: {
    riskSortedItems(state): BatchImportItem[] {
      return [...state.items].sort((a, b) => rank(a) - rank(b))
    },
    highConfidenceIds(state): string[] {
      return state.items
        .filter((i) => i.status === 'review' && i.summary.confidence_tier === 'high')
        .map((i) => i.id)
    },
    inProgress(state): boolean {
      return state.items.some((i) => ['queued', 'parsing', 'applying'].includes(i.status))
    },
    currentItem(state): BatchImportItem | null {
      return state.items.find((i) => i.id === state.currentItemId) ?? null
    },
  },

  actions: {
    async load(jobId: string): Promise<void> {
      this.jobId = jobId
      this.loading = true
      try {
        await this.refresh()
      } finally {
        this.loading = false
      }
    },

    async refresh(): Promise<void> {
      if (!this.jobId) return
      this.job = await api.fetchBatchJob(this.jobId)
      this.items = await api.fetchBatchItems(this.jobId, this.statusFilter ?? undefined)
    },

    startPolling(): void {
      if (this.polling !== null) return
      this.polling = window.setInterval(() => {
        void (async () => {
          await this.refresh()
          if (!this.inProgress) this.stopPolling()
        })()
      }, 3000)
    },

    stopPolling(): void {
      if (this.polling !== null) {
        window.clearInterval(this.polling)
        this.polling = null
      }
    },

    async openItem(itemId: string): Promise<void> {
      if (!this.jobId) return
      this.currentItemId = itemId
      this.blob = await api.fetchParseResult(this.jobId, itemId)
      // 读条目真实版本（而非硬编码 1）：避免重开已改判过的条目时首个 op 必然 409
      this.reviewRevision = this.currentItem?.review_revision ?? 1
    },

    async reloadBlob(): Promise<void> {
      if (this.jobId && this.currentItemId) {
        this.blob = await api.fetchParseResult(this.jobId, this.currentItemId)
      }
    },

    async applyReviewOps(ops: ReviewOp[]): Promise<void> {
      if (!this.jobId || !this.currentItemId) return
      try {
        const res = await api.patchReviewItem(this.jobId, this.currentItemId, {
          review_revision: this.reviewRevision, ops,
        })
        this.reviewRevision = res.review_revision
        await this.reloadBlob()
      } catch (err) {
        if (isVersionConflict(err)) {
          ElMessage.warning('该条目已被修改，已为你刷新最新内容')
          // reload-wins：拉权威版本（而非盲猜 +1），多端并发改判时才正确
          await this.refresh()
          this.reviewRevision = this.currentItem?.review_revision ?? this.reviewRevision + 1
          await this.reloadBlob()
          return
        }
        throw err
      }
    },

    async preview(itemIds: string[] | null): Promise<ApplyPreview> {
      if (!this.jobId) throw new Error('no job')
      return api.previewApply(this.jobId, itemIds)
    },

    async apply(opts: { itemIds?: string[] | null; highConfidenceOnly?: boolean }): Promise<void> {
      if (!this.jobId) return
      await api.applyBatch(this.jobId, opts)
      await this.refresh()
      this.startPolling()
    },

    async retry(itemId: string): Promise<void> {
      if (!this.jobId) return
      await api.retryItem(this.jobId, itemId)
      await this.refresh()
      this.startPolling()
    },

    async skip(itemId: string): Promise<void> {
      if (!this.jobId) return
      await api.skipItem(this.jobId, itemId)
      await this.refresh()
    },

    async undo(itemId: string): Promise<void> {
      if (!this.jobId) return
      await api.undoItem(this.jobId, itemId)
      await this.refresh()
    },

    selectPrev(): void {
      const ids = this.riskSortedItems.map((i) => i.id)
      const idx = ids.indexOf(this.currentItemId ?? '')
      this.currentItemId = ids[Math.max(0, idx - 1)] ?? ids[0] ?? null
    },

    selectNext(): void {
      const ids = this.riskSortedItems.map((i) => i.id)
      const idx = ids.indexOf(this.currentItemId ?? '')
      this.currentItemId = ids[Math.min(ids.length - 1, idx + 1)] ?? null
    },
  },
})
