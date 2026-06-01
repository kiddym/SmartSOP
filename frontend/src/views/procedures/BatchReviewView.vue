<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useBatchReviewStore } from '@/store/batchReview'
import { useVirtualRows } from '@/composables/useVirtualRows'
import { useBatchReviewShortcuts } from '@/composables/useBatchReviewShortcuts'
import BatchReviewRow from '@/components/batch/BatchReviewRow.vue'
import ReviewDrawer from '@/components/batch/ReviewDrawer.vue'
import ApplyPreviewDialog from '@/components/batch/ApplyPreviewDialog.vue'

const route = useRoute()
const store = useBatchReviewStore()

const rowsEl = ref<HTMLElement | null>(null)
const drawerVisible = ref(false)
const previewVisible = ref(false)
const previewItemIds = ref<string[] | null>(null)

const rows = computed(() => store.riskSortedItems)
const { start, end, padTop, padBottom, totalHeight } = useVirtualRows(rowsEl, () => rows.value.length)

onMounted(async () => {
  await store.load(route.params.jobId as string)
  if (store.inProgress) store.startPolling()
})
onUnmounted(() => store.stopPolling())

async function openPreview(itemId: string): Promise<void> {
  await store.openItem(itemId)
  drawerVisible.value = true
}

function openApplyPreview(itemIds: string[] | null): void {
  previewItemIds.value = itemIds
  previewVisible.value = true
}

async function confirmApply(): Promise<void> {
  await store.apply({ itemIds: previewItemIds.value })
  previewVisible.value = false
  ElMessage.success('已提交应用，后台落库中')
}

function applyAllHighConfidence(): void {
  openApplyPreview(store.highConfidenceIds)
}

useBatchReviewShortcuts({
  onPrev: () => store.selectPrev(),
  onNext: () => store.selectNext(),
  onOpen: () => { if (store.currentItemId) void openPreview(store.currentItemId) },
  onApply: () => { if (store.currentItemId) openApplyPreview([store.currentItemId]) },
  onSkip: () => { if (store.currentItemId) void store.skip(store.currentItemId) },
})
</script>

<template>
  <div class="batch-review">
    <header v-if="store.job" class="summary">
      <span>待确认 {{ store.job.counts.review }}</span>
      <span>已应用 {{ store.job.counts.applied }}</span>
      <span>失败 {{ store.job.counts.failed }}</span>
      <el-button
        type="primary"
        :disabled="!store.highConfidenceIds.length"
        @click="applyAllHighConfidence"
      >全选高置信并应用（{{ store.highConfidenceIds.length }}）</el-button>
    </header>

    <div ref="rowsEl" class="rows" :style="{ height: '70vh', overflow: 'auto' }">
      <div :style="{ height: totalHeight + 'px', position: 'relative' }">
        <div :style="{ height: padTop + 'px' }" />
        <BatchReviewRow
          v-for="item in rows.slice(start, end)"
          :key="item.id"
          :item="item"
          :selected="item.id === store.currentItemId"
          @open="openPreview(item.id)"
          @edit="openPreview(item.id)"
          @apply="openApplyPreview([item.id])"
          @skip="store.skip(item.id)"
          @retry="store.retry(item.id)"
        />
        <div :style="{ height: padBottom + 'px' }" />
      </div>
    </div>

    <ReviewDrawer v-model="drawerVisible" />
    <ApplyPreviewDialog
      v-model="previewVisible"
      :item-ids="previewItemIds"
      @confirm="confirmApply"
    />
  </div>
</template>
