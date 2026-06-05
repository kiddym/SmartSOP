<script setup lang="ts">
import { computed } from 'vue'
import type { ProcedureStatus } from '@/types/procedure'

const props = defineProps<{ status: ProcedureStatus }>()

const LABELS: Record<ProcedureStatus, string> = {
  DRAFT: '草稿',
  PUBLISHED: '已发布',
  ARCHIVED: '已归档',
}

const label = computed(() => LABELS[props.status])
const klass = computed(() => `status-${props.status.toLowerCase()}`)
</script>

<template>
  <span class="status-tag" :class="klass">
    <span class="dot" />
    {{ label }}
  </span>
</template>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  /* 状态枚举属于数据字段，走等宽（docs/design-system.md §2.2）。 */
  font-family: var(--font-mono);
}
/* 胶囊底色：各状态色 12% 浅染（不新增配色令牌，用现有 st-*） */
.status-draft {
  background: color-mix(in srgb, var(--st-draft) 12%, transparent);
  /* 文字向主文色加深，提升浅底上的对比度（WCAG AA） */
  color: color-mix(in srgb, var(--st-draft) 65%, var(--text-primary));
}
.status-published {
  background: color-mix(in srgb, var(--st-published) 14%, transparent);
  color: color-mix(in srgb, var(--st-published) 70%, var(--text-primary));
}
.status-archived {
  background: color-mix(in srgb, var(--st-archived) 14%, transparent);
  color: color-mix(in srgb, var(--st-archived) 80%, var(--text-primary));
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
/* DRAFT = 空心暖灰点；PUBLISHED = 实心鼠尾草绿；ARCHIVED = 暗实心 */
.status-draft .dot {
  background: transparent;
  border: 1px solid var(--st-draft);
}
.status-published .dot {
  background: var(--st-published);
}
.status-archived .dot {
  background: var(--st-archived);
}
</style>
