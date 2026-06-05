<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import PartsView from './PartsView.vue'
import MultiPartsView from './MultiPartsView.vue'

const route = useRoute()
const router = useRouter()

// tab 与路由双向绑定：/inventory/parts → parts，/inventory/parts/kits → kits。
const activeTab = computed<string>(() => (route.path.endsWith('/kits') ? 'kits' : 'parts'))

function onTabChange(name: string | number): void {
  const target = name === 'kits' ? '/inventory/parts/kits' : '/inventory/parts'
  if (route.path !== target) void router.push(target)
}
</script>

<template>
  <div class="page">
    <h2 class="page-title">备件库存</h2>
    <el-tabs :model-value="activeTab" @update:model-value="onTabChange">
      <el-tab-pane label="备件库存" name="parts">
        <PartsView v-if="activeTab === 'parts'" embedded />
      </el-tab-pane>
      <el-tab-pane label="多备件套件" name="kits">
        <MultiPartsView v-if="activeTab === 'kits'" embedded />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
