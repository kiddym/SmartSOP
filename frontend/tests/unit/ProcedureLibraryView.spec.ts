import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import type { FolderTreeNode } from '@/types/folder'

// 直接 mock store 模块，避开 @pinia/testing 依赖（未装）。
// 这些测试只关心 view 的本地 state；store 调用 mock 成 noop 即可。
vi.mock('@/store/procedures', () => ({
  useProcedureStore: () => ({
    loadList: vi.fn().mockResolvedValue(undefined),
    rows: [],
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
  }),
}))

// dynamic import 必须在 mock 之后，否则 store import 不被拦截
const { default: ProcedureLibraryView } = await import(
  '@/views/procedures/ProcedureLibraryView.vue'
)

const normalFolder: FolderTreeNode = {
  id: 'f-normal', name: 'QC', prefix: 'QC', parent_id: null, system: false,
  full_path: 'QC', created_at: '', updated_at: '',
  procedure_count: 0, children: [],
}
const archiveFolder: FolderTreeNode = {
  id: 'f-archive', name: '归档', prefix: '', parent_id: null, system: true,
  full_path: '归档', created_at: '', updated_at: '',
  procedure_count: 0, children: [],
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/procedures/library', component: { template: '<div/>' } },
      { path: '/procedures/:id', component: { template: '<div/>' } },
    ],
  })
}

async function mountView() {
  const router = makeRouter()
  await router.push('/procedures/library')
  await router.isReady()
  return mount(ProcedureLibraryView, {
    global: {
      plugins: [router],
      stubs: {
        // FolderTreePane / ProcedureTable / 对话框 stub，避免拉真数据
        FolderTreePane: { name: 'FolderTreePane', template: '<div class="ft-stub"/>', emits: ['select'] },
        ProcedureTable: { props: ['rows', 'loading'], template: '<div class="pt-stub"/>', emits: ['open'] },
        CreateProcedureDialog: true,
        CreateFromWordDialog: true,
      },
    },
  })
}

describe('ProcedureLibraryView', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('mount 时无选中文件夹：query.status=PUBLISHED, folder_id=undefined', async () => {
    const w = await mountView()
    const vm = w.vm as unknown as { query: { status: string; folder_id?: string } }
    expect(vm.query.status).toBe('PUBLISHED')
    expect(vm.query.folder_id).toBeUndefined()
  })

  it('选中普通文件夹：query.status=PUBLISHED + folder_id 设入', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', normalFolder)
    const vm = w.vm as unknown as { query: { status: string; folder_id?: string } }
    expect(vm.query.status).toBe('PUBLISHED')
    expect(vm.query.folder_id).toBe('f-normal')
  })

  it('选中 system 文件夹：query.status 自动切到 ARCHIVED', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', archiveFolder)
    const vm = w.vm as unknown as { query: { status: string; folder_id?: string } }
    expect(vm.query.status).toBe('ARCHIVED')
    expect(vm.query.folder_id).toBe('f-archive')
  })

  it('选中 system 文件夹时「新建」按钮隐藏', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', archiveFolder)
    expect(w.find('[data-test="create-btn"]').exists()).toBe(false)
  })

  it('普通文件夹下「新建」按钮显示', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', normalFolder)
    expect(w.find('[data-test="create-btn"]').exists()).toBe(true)
  })
})
