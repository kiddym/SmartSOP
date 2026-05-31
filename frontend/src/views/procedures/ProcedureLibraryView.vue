<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import FolderTreePane from '@/components/library/FolderTreePane.vue'
import ProcedureTable from '@/components/ProcedureTable.vue'
import CreateProcedureDialog from '@/components/CreateProcedureDialog.vue'
import CreateFromWordDialog from '@/components/CreateFromWordDialog.vue'
import { useProcedureStore } from '@/store/procedures'
import type { ProcedureMeta, ProcedureStatus } from '@/types/procedure'
import type { FolderTreeNode } from '@/types/folder'

const router = useRouter()
const store = useProcedureStore()
const createVisible = ref(false)
const wordVisible = ref(false)

const selectedFolder = ref<FolderTreeNode | null>(null)

type StatusFilter = ProcedureStatus | ''

interface LibraryQuery {
  search: string
  status: StatusFilter
  folder_id: string | undefined
  page: number
}

const query = reactive<LibraryQuery>({
  search: '',
  status: '',
  folder_id: undefined,
  page: 1,
})

async function load(): Promise<void> {
  await store.loadList({
    page: query.page,
    page_size: store.pageSize,
    search: query.search || undefined,
    status: query.status || undefined,
    folder_id: query.folder_id,
  })
}

onMounted(load)

function onSelectFolder(node: FolderTreeNode | null): void {
  selectedFolder.value = node
  query.folder_id = node?.id
  query.status = node?.system ? 'ARCHIVED' : ''
  query.page = 1
  void load()
}

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
  void router.push({ path: `/procedures/${id}/edit`, query: { from: 'import' } })
}
</script>

<template>
  <div class="library">
    <FolderTreePane @select="onSelectFolder" />

    <div class="list-pane">
      <div class="toolbar">
        <h2 class="title">{{ selectedFolder?.name ?? '全库' }}</h2>
        <div class="toolbar-actions">
          <el-dropdown
            v-if="!selectedFolder?.system"
            data-test="create-btn"
            trigger="click"
            @command="(c: string) => (c === 'word' ? (wordVisible = true) : (createVisible = true))"
          >
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
          :placeholder="`搜索编码 / 名称 / 描述${selectedFolder ? '' : '（跨全库）'}`"
          clearable
          class="search"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <el-select
          v-model="query.status"
          data-test="status-filter"
          class="status-select"
          placeholder="全部状态"
          @change="onSearch"
        >
          <el-option label="全部状态" value="" />
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
  </div>
</template>

<style scoped>
.library {
  display: flex;
  height: 100%;
  min-height: 0;
}
.list-pane {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.title {
  margin: 0;
  font-size: 18px;
}
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.search {
  flex: 1;
  max-width: 400px;
}
.status-select {
  width: 140px;
  flex: 0 0 auto;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
