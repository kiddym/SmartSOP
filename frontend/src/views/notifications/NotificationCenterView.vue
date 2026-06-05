<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as api from '@/api/notifications'
import { useNotificationStore } from '@/store/notifications'
import { formatNotification, entityRoute, NOTIFICATION_TYPES } from '@/utils/notificationText'
import { relativeTime } from '@/utils/format'
import NotificationPreferences from '@/components/notifications/NotificationPreferences.vue'
import type { Notification } from '@/types/notification'

const router = useRouter()
const store = useNotificationStore()

const tab = ref<'list' | 'prefs'>('list')
const items = ref<Notification[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filter = ref<'all' | 'unread'>('all')
const typeFilter = ref<string>('')
const loading = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await api.listNotifications({
      page: page.value,
      page_size: pageSize,
      ...(filter.value === 'unread' ? { is_read: false } : {}),
      ...(typeFilter.value ? { type: typeFilter.value } : {}),
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function setFilter(v: string | number | boolean): Promise<void> {
  filter.value = v as 'all' | 'unread'
  page.value = 1
  return load()
}
function setType(v: string | number | boolean): void {
  typeFilter.value = String(v ?? '')
  page.value = 1
  void load()
}
function onPage(p: number): void {
  page.value = p
  void load()
}
async function onItem(n: Notification): Promise<void> {
  await store.markRead(n.id)
  n.is_read = true
  const to = entityRoute(n)
  if (to) router.push(to)
}
async function onMarkAll(): Promise<void> {
  await store.markAllRead()
  await load()
}

onMounted(load)
defineExpose({ setFilter, setType, onPage, onMarkAll })
</script>

<template>
  <div class="notif-center">
    <h2>通知中心</h2>
    <el-tabs v-model="tab">
      <el-tab-pane label="通知" name="list">
        <div class="notif-toolbar">
          <el-radio-group :model-value="filter" @update:model-value="(v: string | number | boolean) => setFilter(v)">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="unread">未读</el-radio-button>
          </el-radio-group>
          <el-select :model-value="typeFilter" placeholder="全部类型" clearable @update:model-value="(v: string | number | boolean) => setType(v)">
            <el-option v-for="t in NOTIFICATION_TYPES" :key="t.code" :label="t.label" :value="t.code" />
          </el-select>
          <span class="spacer" />
          <el-button size="small" :disabled="store.unreadCount === 0" @click="onMarkAll">全部已读</el-button>
        </div>
        <el-empty v-if="items.length === 0" description="暂无通知" />
        <ul v-else v-loading="loading" class="notif-rows">
          <li
            v-for="n in items"
            :key="n.id"
            class="notif-row"
            :class="{ unread: !n.is_read }"
            @click="onItem(n)"
          >
            <span v-if="!n.is_read" class="dot" />
            <span class="msg">{{ formatNotification(n) }}</span>
            <span class="time">{{ relativeTime(n.created_at) }}</span>
          </li>
        </ul>
        <el-pagination
          v-if="total > pageSize"
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPage"
        />
      </el-tab-pane>
      <el-tab-pane label="偏好设置" name="prefs">
        <NotificationPreferences />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.notif-center { padding: 4px 2px; }
.notif-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.notif-toolbar .spacer { flex: 1; }
.notif-rows { list-style: none; margin: 0; padding: 0; }
.notif-row { display: flex; align-items: center; gap: 10px; padding: 12px; border-bottom: 1px solid var(--border-subtle); cursor: pointer; }
.notif-row:hover { background: var(--bg-hover); }
.notif-row.unread .msg { color: var(--text-primary); font-weight: 500; }
.notif-row .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
.notif-row .msg { flex: 1; }
.notif-row .time { color: var(--text-tertiary); font-size: 12px; flex-shrink: 0; }
</style>
