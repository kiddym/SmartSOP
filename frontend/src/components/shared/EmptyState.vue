<script setup lang="ts">
import type { Component } from 'vue'
import { ElIcon } from 'element-plus'

// 统一空状态（design-system.md §3.9）：居中线性图标 + 文案 + 可选 CTA。
// 用法：作为 el-table 的 #empty slot，或整页无数据时的占位。
// CTA 放默认插槽，例如 <EmptyState ...><el-button>新建</el-button></EmptyState>。
withDefaults(
  defineProps<{
    icon?: Component
    title?: string
    description?: string
  }>(),
  { title: '暂无数据' },
)
</script>

<template>
  <div class="empty-state">
    <el-icon v-if="icon" class="empty-icon"><component :is="icon" /></el-icon>
    <p class="empty-title">{{ title }}</p>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-cta"><slot /></div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 40px 16px;
  text-align: center;
}
.empty-icon {
  font-size: 40px;
  color: #c8bfb2;
  margin-bottom: 2px;
}
.empty-title {
  margin: 0;
  font-size: 14px;
  color: #6b635a;
}
.empty-desc {
  margin: 0;
  font-size: 12px;
  color: #9a8e80;
}
.empty-cta {
  margin-top: 10px;
}
</style>
