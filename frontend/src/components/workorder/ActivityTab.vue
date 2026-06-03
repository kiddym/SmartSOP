<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listWorkOrderActivities, addWorkOrderComment } from '@/api/workOrders'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/store/auth'
import { formatDateTime } from '@/utils/format'
import type { WorkOrderActivityRead } from '@/types/workOrder'
import type { UserRead } from '@/types/platform'

const props = defineProps<{ workOrderId: string }>()

const auth = useAuthStore()

// ── constants ──────────────────────────────────────────────
const WO_STATUS_LABELS: Record<string, string> = {
  OPEN: '待处理',
  IN_PROGRESS: '进行中',
  ON_HOLD: '挂起',
  COMPLETE: '已完成',
  CANCELED: '已取消',
}

// ── helpers ────────────────────────────────────────────────
function statusText(s: string | null): string {
  return s ? (WO_STATUS_LABELS[s] ?? s) : '—'
}

function userName(id: string | null): string {
  if (!id) return '—'
  const u = users.value.find((x) => x.id === id)
  return u ? u.name : '—'
}

// ── state ──────────────────────────────────────────────────
const activities = ref<WorkOrderActivityRead[]>([])
const users = ref<UserRead[]>([])
const commentText = ref('')
const loading = ref(false)
const submitting = ref(false)

// ── load ───────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    activities.value = await listWorkOrderActivities(props.workOrderId)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([listUsers().then((v) => (users.value = v)), load()])
})

// ── submit comment ─────────────────────────────────────────
async function submitComment() {
  if (!commentText.value.trim()) return
  try {
    submitting.value = true
    await addWorkOrderComment(props.workOrderId, { comment: commentText.value.trim() })
    commentText.value = ''
    await load()
  } catch {
    ElMessage.error('操作失败，请重试')
  } finally {
    submitting.value = false
  }
}

defineExpose({ commentText, submitComment, load })
</script>

<template>
  <div class="activity-tab">
    <el-timeline v-loading="loading">
      <el-timeline-item
        v-for="a in activities"
        :key="a.id"
        :timestamp="formatDateTime(a.created_at)"
        placement="top"
      >
        <template v-if="a.activity_type === 'STATUS_CHANGE'">
          {{ userName(a.actor_user_id) }} {{ statusText(a.from_status) }} →
          {{ statusText(a.to_status) }}
        </template>
        <template v-else-if="a.activity_type === 'COMMENT'">
          {{ userName(a.actor_user_id) }}：{{ a.comment }}
        </template>
        <template v-else>
          {{ userName(a.actor_user_id) }} {{ a.activity_type
          }}{{ a.comment ? '：' + a.comment : '' }}
        </template>
      </el-timeline-item>
    </el-timeline>

    <div class="comment-box">
      <el-input v-model="commentText" type="textarea" placeholder="请输入评论" :rows="3" />
      <el-button
        v-if="auth.hasPermission('work_order.view')"
        type="primary"
        :loading="submitting"
        style="margin-top: 8px"
        @click="submitComment"
      >
        发表评论
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.activity-tab {
  padding: 16px;
}

.comment-box {
  margin-top: 16px;
}
</style>
