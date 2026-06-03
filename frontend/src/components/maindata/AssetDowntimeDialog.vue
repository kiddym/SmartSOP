<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listDowntimes, addDowntime, closeDowntime } from '@/api/assets'
import type { DowntimeRead } from '@/types/maindata'
import { useAuthStore } from '@/store/auth'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  visible: boolean
  asset: { id: string; name: string } | null
  nameOf: (id: string | null) => string
}>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const downtimes = ref<DowntimeRead[]>([])

async function fetchDowntimes() {
  if (!props.asset) return
  loading.value = true
  try {
    downtimes.value = await listDowntimes(props.asset.id)
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v && props.asset) fetchDowntimes()
  },
  { immediate: true },
)

// ── add downtime form ──────────────────────────────────────
const addVisible = ref(false)
const submitting = ref(false)
const addForm = reactive<{ started_at: string; reason: string }>({
  started_at: '',
  reason: '',
})

function openAdd() {
  addForm.started_at = ''
  addForm.reason = ''
  addVisible.value = true
}

async function submitAdd() {
  if (!props.asset) return
  if (!addForm.started_at) {
    ElMessage.warning('请选择开始时间')
    return
  }
  submitting.value = true
  try {
    await addDowntime(props.asset.id, {
      started_at: addForm.started_at,
      reason: addForm.reason,
    })
    ElMessage.success('保存成功')
    addVisible.value = false
    await fetchDowntimes()
    emit('changed')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── close downtime form ────────────────────────────────────
const closeVisible = ref(false)
const closingId = ref<string | null>(null)
const closeForm = reactive<{ ended_at: string }>({ ended_at: '' })

function openClose(row: DowntimeRead) {
  closingId.value = row.id
  // 默认以该行开始时间作为结束时间，保证非空可直接提交（避免使用 new Date()）。
  closeForm.ended_at = row.started_at
  closeVisible.value = true
}

async function submitClose() {
  if (!props.asset || !closingId.value) return
  if (!closeForm.ended_at) {
    ElMessage.warning('请选择结束时间')
    return
  }
  submitting.value = true
  try {
    await closeDowntime(props.asset.id, closingId.value, { ended_at: closeForm.ended_at })
    ElMessage.success('已关闭')
    closeVisible.value = false
    await fetchDowntimes()
    emit('changed')
  } catch {
    ElMessage.error('操作失败，请重试')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="'停机记录 — ' + (asset?.name ?? '')"
    width="720px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('asset.edit')" type="primary" @click="openAdd">
        新增停机
      </el-button>
    </div>

    <el-table v-loading="loading" :data="downtimes" border style="width: 100%; margin-top: 12px">
      <el-table-column label="开始" min-width="150">
        <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="结束" min-width="150">
        <template #default="{ row }">
          {{ row.ended_at ? formatDateTime(row.ended_at) : '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="reason" label="原因" min-width="160" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          {{ row.downtime_type === 'manual' ? '手动' : '级联' }}
        </template>
      </el-table-column>
      <el-table-column label="来源" min-width="140">
        <template #default="{ row }">{{ nameOf(row.source_asset_id) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center">
        <template #default="{ row }">
          <el-button
            v-if="row.ended_at == null && auth.hasPermission('asset.edit')"
            link
            type="primary"
            @click="openClose(row)"
          >
            关闭
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button @click="emit('update:visible', false)">关闭对话框</el-button>
    </template>
  </el-dialog>

  <!-- add downtime form dialog -->
  <el-dialog
    v-model="addVisible"
    title="新增停机"
    width="480px"
    append-to-body
    :close-on-click-modal="false"
  >
    <el-form label-width="90px" @submit.prevent="submitAdd">
      <el-form-item label="开始时间" required>
        <el-date-picker
          v-model="addForm.started_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="请选择开始时间"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="原因">
        <el-input v-model="addForm.reason" placeholder="请输入停机原因" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="addVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitAdd">保存</el-button>
    </template>
  </el-dialog>

  <!-- close downtime form dialog -->
  <el-dialog
    v-model="closeVisible"
    title="关闭停机"
    width="480px"
    append-to-body
    :close-on-click-modal="false"
  >
    <el-form label-width="90px" @submit.prevent="submitClose">
      <el-form-item label="结束时间" required>
        <el-date-picker
          v-model="closeForm.ended_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="请选择结束时间"
          style="width: 100%"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="closeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitClose">确认关闭</el-button>
    </template>
  </el-dialog>
</template>
