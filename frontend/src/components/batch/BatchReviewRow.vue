<script setup lang="ts">
import { computed } from 'vue'
import type { BatchImportItem } from '@/types/batchImport'

const props = defineProps<{ item: BatchImportItem; selected: boolean }>()
const emit = defineEmits<{ open: []; apply: []; edit: []; retry: []; skip: [] }>()

const STATUS_LABEL: Record<string, string> = {
  queued: '排队', parsing: '解析中', review: '待确认',
  applying: '应用中', applied: '已应用', skipped: '已跳过', failed: '失败',
}
const TIER_CLASS: Record<string, string> = { high: 'tier-high', medium: 'tier-mid', low: 'tier-low' }

const tier = computed(() => props.item.summary.confidence_tier ?? 'high')
const isReview = computed(() => props.item.status === 'review')
const isFailed = computed(() => props.item.status === 'failed')
</script>

<template>
  <div class="brow" :class="{ selected }">
    <span class="status-chip" :data-status="item.status">{{ STATUS_LABEL[item.status] }}</span>
    <span class="filename" :title="item.filename">{{ item.filename }}</span>
    <span class="tier-bar" :class="TIER_CLASS[tier]" />
    <span class="chapters">{{ item.summary.chapter_count ?? '-' }}</span>
    <span v-if="item.summary.warning_count" class="warnings">{{ item.summary.warning_count }}⚠</span>
    <span class="actions">
      <el-button v-if="isReview" size="small" data-test="preview" @click="emit('open')">预览</el-button>
      <el-button v-if="isReview" size="small" data-test="edit" @click="emit('edit')">精审</el-button>
      <el-button v-if="isReview" size="small" type="primary" data-test="apply" @click="emit('apply')">应用</el-button>
      <el-button v-if="isReview" size="small" data-test="skip" @click="emit('skip')">跳过</el-button>
      <el-button v-if="isFailed" size="small" data-test="retry" @click="emit('retry')">重试</el-button>
    </span>
  </div>
</template>

<style scoped>
.brow { display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 8px; }
.brow.selected { background: var(--el-color-primary-light-9); }
.filename { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tier-bar { width: 4px; height: 16px; border-radius: 2px; }
.tier-high { background: var(--el-color-success); }
.tier-mid { background: var(--el-color-warning); }
.tier-low { background: var(--el-color-danger); }
.warnings { color: var(--el-color-warning); font-size: 12px; }
.status-chip { font-size: 12px; color: var(--el-text-color-secondary); }
.actions { display: flex; gap: 4px; }
</style>
