<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useBatchReviewStore } from '@/store/batchReview'
import type { ApplyPreview } from '@/types/batchImport'

const props = defineProps<{ modelValue: boolean; itemIds: string[] | null }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; confirm: [] }>()

const store = useBatchReviewStore()
const preview = ref<ApplyPreview | null>(null)
const loading = ref(false)

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      loading.value = true
      store.preview(props.itemIds).then((result) => {
        preview.value = result
      }).finally(() => {
        loading.value = false
      })
    }
  },
  { immediate: true },
)
</script>

<template>
  <el-dialog v-model="visible" title="应用前确认" width="460px">
    <div v-if="preview" v-loading="loading">
      <p>将应用 <strong>{{ preview.to_create }}</strong> 份到目标文件夹</p>
      <p>· {{ preview.to_create }} 份新建程序</p>
      <p v-if="preview.duplicate_skip">· {{ preview.duplicate_skip }} 份内容重复 → 跳过</p>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!preview || !preview.to_create" @click="emit('confirm')">
        确认应用
      </el-button>
    </template>
  </el-dialog>
</template>
