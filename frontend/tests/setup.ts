// 测试环境补齐 Web Storage：本仓库的 jsdom 下 localStorage 是无方法的空对象
// （useStorage 运行时被 vueuse 吞错降级，但测试里显式调用 localStorage.clear() 会抛）。
class StorageMock implements Storage {
  private store = new Map<string, string>()
  get length(): number {
    return this.store.size
  }
  clear(): void {
    this.store.clear()
  }
  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value))
  }
  removeItem(key: string): void {
    this.store.delete(key)
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null
  }
}

for (const name of ['localStorage', 'sessionStorage'] as const) {
  Object.defineProperty(globalThis, name, {
    value: new StorageMock(),
    writable: true,
    configurable: true,
  })
}
