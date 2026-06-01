<script setup lang="ts"></script>

<template>
  <div class="auth-layout">
    <div class="auth-card">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.auth-layout { display: flex; align-items: center; justify-content: center; min-height: 100vh; background: var(--el-fill-color-light, #f5f7fa); }
.auth-card { width: 360px; padding: 32px; background: #fff; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,.08); }
</style>
