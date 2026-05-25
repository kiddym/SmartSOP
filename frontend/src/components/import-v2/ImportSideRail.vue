<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ label: string; side: 'left' | 'right' }>()
const emit = defineEmits<{ (e: 'expand'): void }>()

// 箭头朝向"面板展开的方向"：左条向右开 »，右条向左开 «。
const arrow = computed(() => (props.side === 'left' ? '»' : '«'))
</script>

<template>
  <div :class="['rail', side === 'left' ? 'rail-left' : 'rail-right']" :title="`展开${label}`" @click="emit('expand')">
    <span class="rail-expand">{{ arrow }}</span>
    <span class="rail-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.rail {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  cursor: pointer;
  background: var(--el-fill-color-light, #f5f7fa);
  user-select: none;
  color: #606266;
}
.rail-left { border-right: 1px solid var(--el-border-color-lighter, #ebeef5); }
.rail-right { border-left: 1px solid var(--el-border-color-lighter, #ebeef5); }
.rail:hover { background: var(--el-fill-color, #f0f2f5); color: var(--el-color-primary, #d97757); }
.rail-expand { font-size: 14px; line-height: 1; }
.rail-label {
  writing-mode: vertical-rl;
  letter-spacing: 2px;
  font-size: 12px;
  font-weight: 600;
}
</style>
