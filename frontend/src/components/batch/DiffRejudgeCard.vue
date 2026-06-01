<script setup lang="ts">
import { computed } from 'vue'
import type { ParsedNode } from '@/types/parse'
import type { ReviewOp } from '@/types/batchImport'

const props = defineProps<{ node: ParsedNode }>()
const emit = defineEmits<{ op: [ReviewOp] }>()

const TIER_LABEL: Record<string, string> = { high: '高', medium: '中', low: '低' }
const recognized = computed(() =>
  props.node.content_type === 'chapter' ? `${props.node.level} 级章节` : '正文',
)

function emitOp(action: ReviewOp['action'], level?: number): void {
  emit('op', level === undefined
    ? { node_id: props.node.id, action }
    : { node_id: props.node.id, action, level })
}
</script>

<template>
  <div class="rejudge-card" :class="`tier-${node.confidence_tier}`">
    <div class="line">
      <span class="warn">⚠</span>
      <span class="title">{{ node.title || '（正文片段）' }}</span>
      <span class="judged">→ 识别为 {{ recognized }}（置信 {{ TIER_LABEL[node.confidence_tier] }}）</span>
    </div>
    <div class="ops">
      <el-button size="small" data-test="accept" @click="emitOp('accept')">接受</el-button>
      <el-button size="small" data-test="to-content" @click="emitOp('to_content')">改为正文</el-button>
      <el-button size="small" data-test="to-chapter" @click="emitOp('to_chapter')">改为章节</el-button>
      <el-button size="small" data-test="lvl1" @click="emitOp('set_level', 1)">改为一级</el-button>
    </div>
  </div>
</template>

<style scoped>
.rejudge-card { padding: 8px; border-left: 3px solid var(--el-border-color); margin-bottom: 8px; }
.rejudge-card.tier-low { border-left-color: var(--el-color-danger); }
.rejudge-card.tier-medium { border-left-color: var(--el-color-warning); }
.line { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.title { font-weight: 600; }
.judged { color: var(--el-text-color-secondary); font-size: 12px; }
.ops { display: flex; gap: 4px; }
</style>
