<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'

const route = useRoute()
// 公开认证路由（登录/注册）用无壳布局：直接渲染 RouterView（视图自带 AuthLayout 居中卡片），
// 不挂 AppTopBar/AppSidebar 外壳。
const PUBLIC_NAMES = new Set(['login', 'register', 'forgot-password', 'reset-password', 'accept-invite', 'verify-email'])
const isPublicLayout = computed(() => typeof route.name === 'string' && PUBLIC_NAMES.has(route.name))
</script>

<template>
  <RouterView v-if="isPublicLayout" />
  <AppLayout v-else />
</template>
