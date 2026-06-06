<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Delete, Refresh, View, Hide } from '@element-plus/icons-vue'
import {
  listFileLibrary,
  setAttachmentHidden,
  downloadAttachment,
  deleteAttachment,
} from '@/api/attachments'
import type { LibraryAttachment } from '@/types/attachment'
import { formatDateTime } from '@/utils/format'

// 全局文件库：当前 company 下跨实体浏览全部附件（任意认证用户可读，租户隔离）。

// 实体类型中文标签（与后端 ENTITY_REGISTRY 一致；未知回退原值）。
const ENTITY_LABELS: Record<string, string> = {
  procedure: '程序',
  work_order: '工单',
  asset: '资产',
  location: '位置',
  part: '备件',
  request: '请求',
}
function entityLabel(t: string): string {
  return ENTITY_LABELS[t] ?? t
}

const FILE_TYPE_LABELS: Record<string, string> = { IMAGE: '图片', OTHER: '其他' }
function fileTypeLabel(t: string): string {
  return FILE_TYPE_LABELS[t] ?? t
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const PAGE_SIZE = 20

const filters = reactive({
  q: '',
  file_type: '',
  entity_type: '',
  include_hidden: false,
})

const rows = ref<LibraryAttachment[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await listFileLibrary({
      q: filters.q.trim() || undefined,
      file_type: filters.file_type || undefined,
      entity_type: filters.entity_type || undefined,
      include_hidden: filters.include_hidden,
      limit: PAGE_SIZE,
      offset: (page.value - 1) * PAGE_SIZE,
    })
    rows.value = res.items
    total.value = res.total
  } catch {
    ElMessage.error('文件库加载失败')
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  void load()
}

function onPageChange(p: number) {
  page.value = p
  void load()
}

async function onToggleHidden(row: LibraryAttachment) {
  const next = !row.hidden
  try {
    await setAttachmentHidden(row.id, next)
    ElMessage.success(next ? '已隐藏' : '已显示')
    await load()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function onDownload(row: LibraryAttachment) {
  try {
    await downloadAttachment(row.id)
  } catch {
    ElMessage.error('下载失败')
  }
}

async function onDelete(row: LibraryAttachment) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.file_name}」？`, '删除文件', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 取消
  }
  try {
    await deleteAttachment(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(load)

// 暴露内部状态/动作供测试驱动。
defineExpose({ filters, rows, total, page, load, onSearch, onToggleHidden })
</script>

<template>
  <div class="file-library">
    <el-card>
      <template #header>
        <span class="title">文件库</span>
      </template>

      <el-form class="filters" :inline="true" @submit.prevent>
        <el-form-item label="关键字">
          <el-input
            v-model="filters.q"
            placeholder="按文件名搜索"
            clearable
            style="width: 200px"
            @keyup.enter="onSearch"
            @clear="onSearch"
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select
            v-model="filters.file_type"
            placeholder="全部"
            clearable
            style="width: 120px"
            @change="onSearch"
          >
            <el-option label="图片" value="IMAGE" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属实体">
          <el-select
            v-model="filters.entity_type"
            placeholder="全部"
            clearable
            style="width: 120px"
            @change="onSearch"
          >
            <el-option
              v-for="(label, value) in ENTITY_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="filters.include_hidden" @change="onSearch">
            含已隐藏
          </el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Refresh" @click="onSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="rows" border>
        <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.file_type === 'IMAGE' ? 'success' : 'info'" size="small">
              {{ fileTypeLabel(row.file_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="所属实体" width="110">
          <template #default="{ row }">{{ entityLabel(row.entity_type) }}</template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.hidden" type="warning" size="small">已隐藏</el-tag>
            <el-tag v-else type="success" size="small">显示中</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link :icon="Download" @click="onDownload(row)">下载</el-button>
            <el-button
              link
              :icon="row.hidden ? View : Hide"
              @click="onToggleHidden(row)"
            >
              {{ row.hidden ? '显示' : '隐藏' }}
            </el-button>
            <el-button link type="danger" :icon="Delete" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <span class="empty">暂无文件</span>
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-if="total > PAGE_SIZE"
          layout="prev, pager, next, total"
          :total="total"
          :page-size="PAGE_SIZE"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.file-library {
  padding: 16px;
}
.title {
  font-weight: 600;
}
.filters {
  margin-bottom: 8px;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.empty {
  color: var(--el-text-color-secondary);
}
</style>
