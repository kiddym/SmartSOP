<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { AuditLogItem, ProcedureAuditLogItem, AuditLogFilter } from '@/types/auditLog'
import {
  getFolderAuditLogs,
  getProcedureAuditLogs,
  exportFolderAuditLogs,
  exportProcedureAuditLogs,
} from '@/api/auditLogs'
import { formatDateTimeSeconds } from '@/utils/format'

// ── Tabs ────────────────────────────────────────────────────────────────────
const activeTab = ref<'folders' | 'procedures'>('folders')

// ── Shared filter state ──────────────────────────────────────────────────────
const folderFilter = reactive<AuditLogFilter & { dateRange: [string, string] | null }>({
  target_id: '',
  action: '',
  ip_address: '',
  dateRange: null,
  page: 1,
  page_size: 20,
})

const procedureFilter = reactive<AuditLogFilter & { dateRange: [string, string] | null }>({
  target_id: '',
  action: '',
  ip_address: '',
  dateRange: null,
  page: 1,
  page_size: 20,
})

// ── Folder logs ──────────────────────────────────────────────────────────────
const folderLogs = ref<AuditLogItem[]>([])
const folderTotal = ref(0)
const folderLoading = ref(false)

async function loadFolderLogs() {
  folderLoading.value = true
  try {
    const params: AuditLogFilter = {
      page: folderFilter.page,
      page_size: folderFilter.page_size,
    }
    if (folderFilter.target_id) params.target_id = folderFilter.target_id
    if (folderFilter.action) params.action = folderFilter.action
    if (folderFilter.ip_address) params.ip_address = folderFilter.ip_address
    if (folderFilter.dateRange) {
      params.date_from = folderFilter.dateRange[0]
      params.date_to = folderFilter.dateRange[1]
    }
    const data = await getFolderAuditLogs(params)
    folderLogs.value = data.items
    folderTotal.value = data.total
  } catch {
    ElMessage.error('加载文件夹审计日志失败')
  } finally {
    folderLoading.value = false
  }
}

function onFolderQuery() {
  folderFilter.page = 1
  loadFolderLogs()
}

function onFolderPageChange(page: number) {
  folderFilter.page = page
  loadFolderLogs()
}

function onFolderExport() {
  const params: Omit<AuditLogFilter, 'page' | 'page_size'> = {}
  if (folderFilter.target_id) params.target_id = folderFilter.target_id
  if (folderFilter.action) params.action = folderFilter.action
  if (folderFilter.ip_address) params.ip_address = folderFilter.ip_address
  if (folderFilter.dateRange) {
    params.date_from = folderFilter.dateRange[0]
    params.date_to = folderFilter.dateRange[1]
  }
  exportFolderAuditLogs(params)
}

// ── Procedure logs ───────────────────────────────────────────────────────────
const procedureLogs = ref<ProcedureAuditLogItem[]>([])
const procedureTotal = ref(0)
const procedureLoading = ref(false)

async function loadProcedureLogs() {
  procedureLoading.value = true
  try {
    const params: AuditLogFilter = {
      page: procedureFilter.page,
      page_size: procedureFilter.page_size,
    }
    if (procedureFilter.target_id) params.target_id = procedureFilter.target_id
    if (procedureFilter.action) params.action = procedureFilter.action
    if (procedureFilter.ip_address) params.ip_address = procedureFilter.ip_address
    if (procedureFilter.dateRange) {
      params.date_from = procedureFilter.dateRange[0]
      params.date_to = procedureFilter.dateRange[1]
    }
    const data = await getProcedureAuditLogs(params)
    procedureLogs.value = data.items
    procedureTotal.value = data.total
  } catch {
    ElMessage.error('加载程序审计日志失败')
  } finally {
    procedureLoading.value = false
  }
}

function onProcedureQuery() {
  procedureFilter.page = 1
  loadProcedureLogs()
}

function onProcedurePageChange(page: number) {
  procedureFilter.page = page
  loadProcedureLogs()
}

function onProcedureExport() {
  const params: Omit<AuditLogFilter, 'page' | 'page_size'> = {}
  if (procedureFilter.target_id) params.target_id = procedureFilter.target_id
  if (procedureFilter.action) params.action = procedureFilter.action
  if (procedureFilter.ip_address) params.ip_address = procedureFilter.ip_address
  if (procedureFilter.dateRange) {
    params.date_from = procedureFilter.dateRange[0]
    params.date_to = procedureFilter.dateRange[1]
  }
  exportProcedureAuditLogs(params)
}

// ── Detail dialog ────────────────────────────────────────────────────────────
const detailVisible = ref(false)
const detailItem = ref<AuditLogItem | ProcedureAuditLogItem | null>(null)

function openDetail(row: AuditLogItem | ProcedureAuditLogItem) {
  detailItem.value = row
  detailVisible.value = true
}

// ── Utilities ────────────────────────────────────────────────────────────────
// 时间统一走 utils/format（裸 UTC → 本地，带秒），与全站一致、不再偏 8 小时。
function formatDateTime(s: string): string {
  return formatDateTimeSeconds(s)
}

function prettyJson(val: Record<string, unknown>): string {
  return JSON.stringify(val, null, 2)
}

// ── Init ─────────────────────────────────────────────────────────────────────
onMounted(() => {
  loadFolderLogs()
  loadProcedureLogs()
})
</script>

<template>
  <div class="audit-logs-page">
    <h2 class="page-title">审计日志</h2>

    <el-tabs v-model="activeTab" class="audit-tabs">
      <!-- ────────────────────── 文件夹日志 ────────────────────── -->
      <el-tab-pane label="文件夹日志" name="folders">
        <!-- Filter bar -->
        <div class="filter-bar">
          <el-input
            v-model="folderFilter.target_id"
            placeholder="Target ID"
            clearable
            class="filter-input"
          />
          <el-input
            v-model="folderFilter.action"
            placeholder="操作类型（逗号分隔）"
            clearable
            class="filter-input"
          />
          <el-date-picker
            v-model="folderFilter.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            class="filter-date"
          />
          <el-input
            v-model="folderFilter.ip_address"
            placeholder="IP 地址"
            clearable
            class="filter-input"
          />
          <el-button type="primary" @click="onFolderQuery">查询</el-button>
          <el-button @click="onFolderExport">导出 CSV</el-button>
        </div>

        <!-- Table -->
        <el-table
          :data="folderLogs"
          v-loading="folderLoading"
          border
          stripe
          class="audit-table"
        >
          <el-table-column prop="target_id" label="Target ID" min-width="220" show-overflow-tooltip />
          <el-table-column prop="action" label="操作" width="160" />
          <el-table-column prop="created_at" label="时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="ip_address" label="IP 地址" width="150" />
          <el-table-column label="详情" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- Pagination -->
        <el-pagination
          v-model:current-page="folderFilter.page"
          :page-size="folderFilter.page_size"
          :total="folderTotal"
          layout="total, prev, pager, next"
          class="audit-pagination"
          @current-change="onFolderPageChange"
        />
      </el-tab-pane>

      <!-- ────────────────────── 程序日志 ────────────────────── -->
      <el-tab-pane label="程序日志" name="procedures">
        <!-- Filter bar -->
        <div class="filter-bar">
          <el-input
            v-model="procedureFilter.target_id"
            placeholder="Target ID"
            clearable
            class="filter-input"
          />
          <el-input
            v-model="procedureFilter.action"
            placeholder="操作类型（逗号分隔）"
            clearable
            class="filter-input"
          />
          <el-date-picker
            v-model="procedureFilter.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            class="filter-date"
          />
          <el-input
            v-model="procedureFilter.ip_address"
            placeholder="IP 地址"
            clearable
            class="filter-input"
          />
          <el-button type="primary" @click="onProcedureQuery">查询</el-button>
          <el-button @click="onProcedureExport">导出 CSV</el-button>
        </div>

        <!-- Table -->
        <el-table
          :data="procedureLogs"
          v-loading="procedureLoading"
          border
          stripe
          class="audit-table"
        >
          <el-table-column prop="target_id" label="Target ID" min-width="220" show-overflow-tooltip />
          <el-table-column prop="action" label="操作" width="160" />
          <el-table-column prop="created_at" label="时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="ip_address" label="IP 地址" width="150" />
          <el-table-column label="详情" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- Pagination -->
        <el-pagination
          v-model:current-page="procedureFilter.page"
          :page-size="procedureFilter.page_size"
          :total="procedureTotal"
          layout="total, prev, pager, next"
          class="audit-pagination"
          @current-change="onProcedurePageChange"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="日志详情" width="700px" draggable>
      <template v-if="detailItem">
        <div class="detail-section">
          <div class="detail-label">修改前 (old_value)</div>
          <pre class="detail-json">{{ prettyJson(detailItem.old_value) }}</pre>
        </div>
        <div class="detail-section">
          <div class="detail-label">修改后 (new_value)</div>
          <pre class="detail-json">{{ prettyJson(detailItem.new_value) }}</pre>
        </div>
        <div class="detail-meta">
          <span><strong>Reason:</strong> {{ detailItem.reason || '-' }}</span>
          <span><strong>User-Agent:</strong> {{ detailItem.user_agent || '-' }}</span>
          <span v-if="'procedure_group_id' in detailItem"><strong>Procedure Group ID:</strong> {{ detailItem.procedure_group_id || '-' }}</span>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.audit-logs-page {
  max-width: 1200px;
  padding: 20px 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #303133);
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
  align-items: center;
}

.filter-input {
  width: 180px;
}

.filter-date {
  width: 260px;
}

.audit-table {
  width: 100%;
}

.audit-pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-label {
  font-weight: 600;
  margin-bottom: 6px;
  color: #606266;
  font-size: 13px;
}

.detail-json {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  overflow: auto;
  max-height: 240px;
  white-space: pre-wrap;
  word-break: break-all;
}

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}
</style>
