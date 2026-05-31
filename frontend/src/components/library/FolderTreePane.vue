<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import FolderTree from '@/components/FolderTree.vue'
import { useFolderStore } from '@/store/folders'
import type { FolderTreeNode } from '@/types/folder'

defineEmits<{
  (e: 'select', node: FolderTreeNode | null): void
}>()

const store = useFolderStore()
const router = useRouter()

function manageFolders(): void {
  void router.push('/folders')
}

onMounted(() => {
  void store.loadTree()
})
</script>

<template>
  <div class="folder-tree-pane">
    <header class="pane-header">
      <span class="title">文件夹</span>
      <el-button
        data-test="manage-folders-btn"
        :icon="Plus"
        size="small"
        text
        title="新建 / 管理文件夹"
        @click="manageFolders"
      />
    </header>
    <div class="tree-body">
      <FolderTree
        :data="store.tree"
        :loading="store.loading"
        @select="(n) => $emit('select', n)"
      />
    </div>
  </div>
</template>

<style scoped>
.folder-tree-pane {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid #e0dbd3;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.pane-header {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 0 14px;
  border-bottom: 1px solid #e0dbd3;
  flex-shrink: 0;
}
.pane-header .title {
  font-size: 12px;
  color: #9a8e80;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tree-body {
  flex: 1;
  overflow: auto;
  padding: 8px 0;
}
</style>
