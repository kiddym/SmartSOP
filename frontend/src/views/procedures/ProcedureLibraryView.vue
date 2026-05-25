<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import ProcedureTable from '@/components/ProcedureTable.vue'
import CreateProcedureDialog from '@/components/CreateProcedureDialog.vue'
import CreateFromWordDialog from '@/components/CreateFromWordDialog.vue'
import { useProcedureStore } from '@/store/procedures'
import type { ProcedureMeta, ProcedureStatus } from '@/types/procedure'

const router = useRouter()
const store = useProcedureStore()
const createVisible = ref(false)
const wordVisible = ref(false)

const query = reactive<{ search: string; status: string; page: number }>({
  search: '',
  status: '',
  page: 1,
})

async function load(): Promise<void> {
  await store.loadList({
    page: query.page,
    page_size: store.pageSize,
    search: query.search || undefined,
    status: (query.status as ProcedureStatus) || undefined,
  })
}

onMounted(load)

function onSearch(): void {
  query.page = 1
  void load()
}

function onPage(page: number): void {
  query.page = page
  void load()
}

function open(id: string): void {
  void router.push(`/procedures/${id}`)
}

function onCreated(proc: ProcedureMeta): void {
  void router.push(`/procedures/${proc.id}/edit`)
}

function onImported(id: string): void {
  void router.push(`/procedures/${id}/edit`)
}
</script>

<template>
  <div class="library">
    <div class="toolbar">
      <h2 class="title">程序库</h2>
      <div class="toolbar-actions">
        <el-dropdown trigger="click" @command="(c: string) => (c === 'word' ? (wordVisible = true) : (createVisible = true))">
          <el-button type="primary">新建</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="blank">空白程序</el-dropdown-item>
              <el-dropdown-item command="word">从 Word 导入</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div class="filters">
      <el-input
        v-model="query.search"
        placeholder="搜索编码 / 名称 / 描述"
        clearable
        class="search"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <el-select
        v-model="query.status"
        placeholder="全部状态"
        clearable
        class="status"
        @change="onSearch"
      >
        <el-option label="草稿" value="DRAFT" />
        <el-option label="已发布" value="PUBLISHED" />
        <el-option label="已归档" value="ARCHIVED" />
      </el-select>
      <el-button @click="onSearch">查询</el-button>
    </div>

    <ProcedureTable :rows="store.rows" :loading="store.loading" @open="open" />

    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="store.total"
      :current-page="store.page"
      :page-size="store.pageSize"
      @current-change="onPage"
    />

    <CreateProcedureDialog v-model="createVisible" @created="onCreated" />
    <CreateFromWordDialog v-model="wordVisible" @imported="onImported" />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 18px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.search {
  width: 320px;
}
.status {
  width: 160px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.library > * {
  animation: u-fade-in 0.28s ease both;
}
.library > *:nth-child(1) {
  animation-delay: 0.02s;
}
.library > *:nth-child(2) {
  animation-delay: 0.06s;
}
.library > *:nth-child(3) {
  animation-delay: 0.1s;
}
.library > *:nth-child(4) {
  animation-delay: 0.14s;
}
@media (prefers-reduced-motion: reduce) {
  .library > * {
    animation: none;
  }
}
</style>
