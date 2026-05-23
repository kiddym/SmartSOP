<script setup lang="ts">
import { computed } from 'vue'
import ChapterDetailCard from './ChapterDetailCard.vue'
import ContentDetailCard from './ContentDetailCard.vue'
import StepAnnotationCard from './StepAnnotationCard.vue'
import { findParent } from '@/utils/importTree'
import type { useImportDialog } from '@/composables/useImportDialog'

const props = defineProps<{ ctx: ReturnType<typeof useImportDialog> }>()

const node = computed(() => props.ctx.selected.value)
const level = computed(() => (node.value ? props.ctx.levelMap.value.get(node.value.id) ?? 1 : 1))
const number = computed(() => (node.value ? props.ctx.numberMap.value[node.value.id] ?? '' : ''))

const childrenSummary = computed(() => {
  if (!node.value) return []
  return node.value.children.map((c) => ({
    id: c.id,
    title: c.title,
    number: props.ctx.numberMap.value[c.id] ?? '',
    kind: c.content_type as 'chapter' | 'content',
  }))
})

const parentSummary = computed(() => {
  if (!node.value) return null
  const p = findParent(props.ctx.tree.value, node.value.id)
  if (!p) return null
  return {
    id: p.id,
    title: p.title,
    number: props.ctx.numberMap.value[p.id] ?? '',
  }
})

function onUpdate(patch: { title?: string; skip_numbering?: boolean }): void {
  props.ctx.updateSelectedFields(patch)
}
function onAcceptReview(): void {
  if (node.value) props.ctx.acceptReview(node.value.id)
}
function onSelectChild(id: string): void {
  props.ctx.selectNode(id)
}
function onClearStep(): void {
  if (node.value) props.ctx.updateSelectedFields({ mark_status: 'unmarked' })
}
</script>

<template>
  <div class="detail-panel">
    <el-empty v-if="!node" description="选择左侧节点查看详情" />
    <template v-else>
      <ChapterDetailCard
        v-if="node.content_type === 'chapter'"
        :node="node"
        :level="level"
        :number="number"
        :children="childrenSummary"
        @update="onUpdate"
        @accept-review="onAcceptReview"
        @select-child="onSelectChild"
      />
      <ContentDetailCard
        v-else
        :node="node"
        :parent="parentSummary"
        @accept-review="onAcceptReview"
        @select-parent="onSelectChild"
      />
      <StepAnnotationCard
        :active="node.mark_status === 'step'"
        @clear="onClearStep"
      />
    </template>
  </div>
</template>

<style scoped>
.detail-panel { height: 100%; overflow-y: auto; }
</style>
