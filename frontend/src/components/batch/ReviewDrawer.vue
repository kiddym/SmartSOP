<script setup lang="ts">
import { computed } from 'vue'
import { useBatchReviewStore } from '@/store/batchReview'
import type { ParsedNode } from '@/types/parse'
import type { ReviewOp } from '@/types/batchImport'
import DiffRejudgeCard from './DiffRejudgeCard.vue'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const store = useBatchReviewStore()
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function flatten(nodes: ParsedNode[]): ParsedNode[] {
  const out: ParsedNode[] = []
  const walk = (ns: ParsedNode[]): void => {
    for (const n of ns) { out.push(n); walk(n.children) }
  }
  walk(nodes)
  return out
}

const allNodes = computed(() => (store.blob ? flatten(store.blob.chapters) : []))
const reviewNodes = computed(() =>
  allNodes.value.filter((n) => n.mark_status === 'review' || n.confidence_tier !== 'high'),
)

async function onOp(op: ReviewOp): Promise<void> {
  await store.applyReviewOps([op])
}
</script>

<template>
  <el-drawer v-model="visible" :title="store.currentItem?.filename ?? '速览'" size="640px">
    <div class="drawer-body">
      <section v-if="reviewNodes.length" class="rejudge">
        <h4>待确认节点（{{ reviewNodes.length }}）</h4>
        <DiffRejudgeCard v-for="n in reviewNodes" :key="n.id" :node="n" @op="onOp" />
      </section>
      <section class="tree">
        <h4>结构预览</h4>
        <div
          v-for="n in allNodes" :key="n.id" class="tree-node"
          :class="{ low: n.confidence_tier === 'low' }"
          :style="{ paddingLeft: (n.level * 12) + 'px' }"
        >{{ n.title || '（正文）' }}</div>
      </section>
    </div>
  </el-drawer>
</template>
