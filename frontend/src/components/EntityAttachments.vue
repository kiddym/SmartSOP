<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listEntityAttachments,
  uploadEntityAttachment,
  downloadAttachment,
  deleteAttachment,
} from '@/api/attachments'
import type { AttachmentOut } from '@/types/attachment'
import { formatDateTime } from '@/utils/format'

// 通用多态附件区：复用 /attachments?entity_type=&entity_id= 端点，供请求/工单/资产等实体挂附件。
const props = defineProps<{
  entityType: string
  entityId: string
  editable?: boolean
}>()

const attachments = ref<AttachmentOut[]>([])
const loading = ref(false)
const uploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

async function fetchAttachments(): Promise<void> {
  if (!props.entityId) {
    attachments.value = []
    return
  }
  loading.value = true
  try {
    attachments.value = await listEntityAttachments(props.entityType, props.entityId)
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
    for (const f of Array.from(input.files)) {
      await uploadEntityAttachment(props.entityType, props.entityId, f)
    }
    await fetchAttachments()
    ElMessage.success('上传成功')
  } catch {
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
}

async function handleDelete(id: string): Promise<void> {
  try {
    await deleteAttachment(id)
    await fetchAttachments()
    ElMessage.success('删除成功')
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

watch(() => props.entityId, fetchAttachments, { immediate: true })

defineExpose({ fetchAttachments, attachments })
</script>

<template>
  <div class="entity-attachments">
    <div v-if="editable" class="toolbar">
      <el-button type="primary" :loading="uploading" @click="triggerUpload">上传附件</el-button>
      <input ref="fileInputRef" type="file" multiple style="display: none" @change="handleFiles" />
    </div>

    <el-table :data="attachments" v-loading="loading" empty-text="暂无附件" style="width: 100%">
      <el-table-column label="文件名" prop="file_name" min-width="180" show-overflow-tooltip />
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ formatSize(row.size_bytes) }}</template>
      </el-table-column>
      <el-table-column label="描述" prop="description" min-width="140" show-overflow-tooltip />
      <el-table-column label="上传时间" width="150">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="130">
        <template #default="{ row }">
          <el-button link @click="downloadAttachment(row.id)">下载</el-button>
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
.entity-attachments {
  padding: 8px 0;
}
.toolbar {
  margin-bottom: 12px;
}
</style>
