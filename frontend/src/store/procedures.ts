import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import {
  fetchProcedureLibrary,
  fetchProcedureList,
  type ProcedureListQuery,
} from '@/api/procedures'
import { errorMessage, isFeatureLocked } from '@/api/http'
import type { ProcedureRow } from '@/types/procedure'

export const useProcedureStore = defineStore('procedures', {
  state: () => ({
    rows: [] as ProcedureRow[],
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
    // 套餐未包含 SOP 时为 true：view 据此展示「升级订阅」引导，
    // 而非把锁定误显示为「暂无程序」空态。
    featureLocked: false,
  }),
  actions: {
    async _runLoad(
      fetcher: (q: ProcedureListQuery) => ReturnType<typeof fetchProcedureList>,
      query: ProcedureListQuery,
    ): Promise<void> {
      this.loading = true
      this.featureLocked = false
      try {
        const res = await fetcher(query)
        this.rows = res.items
        this.total = res.total
        this.page = res.page
        this.pageSize = res.page_size
      } catch (err) {
        // 锁定态：清空列表并打标，由 view 内联引导升级（不弹错误 toast）。
        this.rows = []
        this.total = 0
        if (isFeatureLocked(err)) {
          this.featureLocked = true
        } else {
          ElMessage.error(errorMessage(err) ?? '加载程序列表失败')
        }
      } finally {
        this.loading = false
      }
    },
    async loadList(query: ProcedureListQuery): Promise<void> {
      await this._runLoad(fetchProcedureList, query)
    },
    async loadLibrary(query: ProcedureListQuery): Promise<void> {
      await this._runLoad(fetchProcedureLibrary, query)
    },
  },
})
