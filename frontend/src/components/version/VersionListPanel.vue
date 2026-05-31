<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import { fetchGroupVersions } from '@/api/procedures'
import { formatDateTime } from '@/utils/format'
import type { VersionListItem } from '@/types/procedure'

// 版本列表面板（§22.2 / Q356）：同 group 全部版本，可展开 notes，归档版本可发起回退。
const props = defineProps<{ groupId: string; viewingId: string }>()
const emit = defineEmits<{
  (e: 'view', id: string): void
  (e: 'rollback', targetVersion: number, currentId: string): void
  (e: 'compare', payload: { oldId: string; oldVersion: number; newId: string; newVersion: number }): void
}>()

const items = ref<VersionListItem[]>([])
const loading = ref(false)
const expanded = ref<Set<string>>(new Set())

const selectedIds = ref<string[]>([])
function toggleSelect(id: string): void {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  } else {
    const next = [...selectedIds.value, id]
    if (next.length > 2) next.shift() // cap 2, FIFO
    selectedIds.value = next
  }
}
function clearSel(): void {
  selectedIds.value = []
}
function compareSelected(): void {
  if (selectedIds.value.length !== 2) return
  const picked = selectedIds.value
    .map((id) => items.value.find((v) => v.id === id))
    .filter((v): v is VersionListItem => !!v)
  if (picked.length !== 2) return
  const [a, b] = picked
  const older = a.version <= b.version ? a : b
  const newer = a.version <= b.version ? b : a
  emit('compare', { oldId: older.id, oldVersion: older.version, newId: newer.id, newVersion: newer.version })
  clearSel()
}

// 当前已发布版本（回退动作的发起者；仅当存在时归档版本才显示「回退到此版本」）。
const currentPublished = computed(() =>
  items.value.find((i) => i.is_current && i.status === 'PUBLISHED'),
)
const current = computed(() => items.value.find((i) => i.is_current))

async function reload(): Promise<void> {
  loading.value = true
  try {
    items.value = (await fetchGroupVersions(props.groupId)).items
  } finally {
    loading.value = false
  }
}
onMounted(reload)
defineExpose({ reload })

async function manualRefresh(): Promise<void> {
  try {
    await reload()
    ElMessage.success('已刷新')
  } catch {
    /* http 拦截器已提示错误 */
  }
}

function emitCompare(v: VersionListItem): void {
  if (!current.value) return
  emit('compare', { oldId: v.id, oldVersion: v.version, newId: current.value.id, newVersion: current.value.version })
}

function toggleNotes(id: string): void {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}
</script>

<template>
  <el-card v-loading="loading" shadow="never" class="vpanel">
    <template #header>
      <div class="hd">
        <span>版本列表（{{ items.length }}）</span>
        <el-button text size="small" :loading="loading" @click="manualRefresh">刷新</el-button>
      </div>
    </template>

    <div v-if="selectedIds.length" class="vsel-bar">
      <span>已选 {{ selectedIds.length }} / 2</span>
      <el-button size="small" type="primary" :disabled="selectedIds.length !== 2" @click="compareSelected">对比所选</el-button>
      <el-button size="small" text @click="clearSel">清空</el-button>
    </div>

    <div v-for="v in items" :key="v.id" class="vrow" :class="{ viewing: v.id === viewingId }">
      <div class="line">
        <el-checkbox class="vrow-check" :model-value="selectedIds.includes(v.id)" @change="() => toggleSelect(v.id)" />
        <span class="ver">v{{ v.version }}</span>
        <StatusTag :status="v.status" />
        <el-tag v-if="v.is_current" size="small" type="success" disable-transitions>当前</el-tag>
        <span class="time">{{ formatDateTime(v.created_at) }}</span>
        <span class="spacer" />
        <span class="vrow-actions">
          <el-button
            v-if="v.version_update_notes"
            text
            size="small"
            @click="toggleNotes(v.id)"
          >
            {{ expanded.has(v.id) ? '收起说明' : '更新说明' }}
          </el-button>
          <el-button v-if="v.id !== viewingId" text size="small" @click="emit('view', v.id)">
            查看
          </el-button>
          <el-button
            v-if="!v.is_current && current"
            text
            size="small"
            @click="emitCompare(v)"
          >
            对比当前
          </el-button>
          <el-button
            v-if="currentPublished && v.status === 'ARCHIVED' && !v.is_current"
            text
            size="small"
            type="warning"
            @click="emit('rollback', v.version, currentPublished.id)"
          >
            回退到此版本
          </el-button>
        </span>
      </div>
      <div
        v-if="v.version_update_notes && !expanded.has(v.id)"
        class="notes-preview"
        @click="toggleNotes(v.id)"
      >
        {{ v.version_update_notes_preview || v.version_update_notes }}
      </div>
      <div v-if="expanded.has(v.id)" class="notes">
        {{ v.version_update_notes || '（无更新说明）' }}
      </div>
    </div>

    <el-empty v-if="!loading && !items.length" description="暂无版本" />
  </el-card>
</template>

<style scoped>
.vpanel {
  margin-bottom: 20px;
}
.hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.vrow {
  padding: 8px 4px;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
}
.vrow.viewing {
  background: var(--el-color-primary-light-9, #fbf1ee);
  border-radius: 4px;
}
.line {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ver {
  font-weight: 600;
  min-width: 36px;
}
.time {
  color: #909399;
  font-size: 12px;
}
.spacer {
  flex: 1;
}
/* 行操作：默认隐藏，hover 或正在查看的行显示（减少常驻按钮噪音）。 */
.vrow-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  visibility: hidden;
}
.vrow:hover .vrow-actions,
.vrow.viewing .vrow-actions {
  visibility: visible;
}
.notes {
  margin: 6px 0 2px 46px;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
  white-space: pre-wrap;
}
.notes-preview {
  margin: 4px 0 2px 46px;
  font-size: 12px;
  color: #909399;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vsel-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  margin-bottom: 6px;
  font-size: 13px;
  background: var(--el-color-primary-light-9, #fbf1ee);
  border-radius: 4px;
}
.vrow-check {
  flex: none;
}
</style>
