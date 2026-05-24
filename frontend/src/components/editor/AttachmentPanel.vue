<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listAttachments,
  uploadAttachment,
  downloadAttachment,
  deleteAttachment,
} from '@/api/attachments'
import type { AttachmentOut } from '@/types/attachment'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  procedureId: string
  editable: boolean
}>()

const attachments = ref<AttachmentOut[]>([])
const loading = ref(false)
const uploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

async function fetchAttachments(): Promise<void> {
  loading.value = true
  try {
    attachments.value = await listAttachments(props.procedureId)
  } finally {
    loading.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function triggerUpload(): void {
  fileInputRef.value?.click()
}

async function handleFiles(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return

  uploading.value = true
  try {
    const filesArray = Array.from(input.files)
    await uploadAttachment(props.procedureId, filesArray)
    await fetchAttachments()
    ElMessage.success('上传成功')
  } catch {
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
    // reset so the same file can be re-selected later
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
}

async function handleDelete(id: string): Promise<void> {
  try {
    await deleteAttachment(props.procedureId, id)
    await fetchAttachments()
    ElMessage.success('删除成功')
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

onMounted(fetchAttachments)
</script>

<template>
  <div class="attachment-panel">
    <!-- Limit alerts -->
    <el-alert
      v-if="attachments.length >= 30"
      type="error"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
    >
      已达上限（30 个），无法继续上传
    </el-alert>
    <el-alert
      v-else-if="attachments.length >= 20"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
    >
      已有 {{ attachments.length }} 个附件，接近上限（30 个）
    </el-alert>

    <!-- Upload toolbar (editable only) -->
    <div v-if="editable" class="toolbar">
      <el-button
        type="primary"
        :disabled="attachments.length >= 30"
        :loading="uploading"
        @click="triggerUpload"
      >
        上传附件
      </el-button>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        style="display: none"
        @change="handleFiles"
      />
    </div>

    <!-- Attachment table -->
    <el-table :data="attachments" v-loading="loading" empty-text="暂无附件" style="width: 100%">
      <el-table-column label="文件名" prop="file_name" min-width="180" show-overflow-tooltip />
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ formatSize(row.size_bytes) }}</template>
      </el-table-column>
      <el-table-column label="描述" prop="description" min-width="160" show-overflow-tooltip />
      <el-table-column label="上传者" width="120">
        <template #default="{ row }">{{ row.uploader_name ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="上传时间" width="150">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="130">
        <template #default="{ row }">
          <el-button link @click="downloadAttachment(props.procedureId, row.id)">下载</el-button>
          <el-popconfirm v-if="editable" title="确定删除？" @confirm="handleDelete(row.id)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.attachment-panel {
  padding: 16px 0;
}

.toolbar {
  margin-bottom: 12px;
}
</style>
