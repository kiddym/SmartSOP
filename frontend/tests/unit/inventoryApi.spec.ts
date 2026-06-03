import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, patch, delete: del } }))

import { listParts, listPartsMini, createPart, updatePart, deletePart } from '@/api/parts'
import {
  listPartCategories,
  createPartCategory,
  updatePartCategory,
  deletePartCategory,
} from '@/api/partCategories'
import {
  listPurchaseOrders,
  getPurchaseOrder,
  createPurchaseOrder,
  updatePurchaseOrder,
  deletePurchaseOrder,
  submitPurchaseOrder,
  approvePurchaseOrder,
  rejectPurchaseOrder,
  cancelPurchaseOrder,
  listPurchaseOrderActivities,
} from '@/api/purchaseOrders'
import {
  listPurchaseOrderCategories,
  createPurchaseOrderCategory,
  updatePurchaseOrderCategory,
  deletePurchaseOrderCategory,
} from '@/api/purchaseOrderCategories'
import {
  listVendors,
  listVendorsMini,
  createVendor,
  updateVendor,
  deleteVendor,
} from '@/api/vendors'
import {
  listCustomers,
  listCustomersMini,
  createCustomer,
  updateCustomer,
  deleteCustomer,
} from '@/api/customers'

describe('inventory api', () => {
  beforeEach(() => {
    for (const m of [get, post, patch, del]) m.mockReset().mockResolvedValue({ data: [] })
  })

  // parts
  it('listParts GET /parts (no params)', async () => {
    await listParts()
    expect(get).toHaveBeenCalledWith('/parts', { params: {} })
  })
  it('listParts GET /parts low_stock', async () => {
    await listParts({ low_stock: true })
    expect(get).toHaveBeenCalledWith('/parts', { params: { low_stock: true } })
  })
  it('listPartsMini GET /parts/mini', async () => {
    await listPartsMini()
    expect(get).toHaveBeenCalledWith('/parts/mini')
  })
  it('createPart POST /parts', async () => {
    await createPart({ name: 'P' })
    expect(post).toHaveBeenCalledWith('/parts', { name: 'P' })
  })
  it('updatePart PATCH /parts/{id}', async () => {
    await updatePart('p1', { quantity: '5' })
    expect(patch).toHaveBeenCalledWith('/parts/p1', { quantity: '5' })
  })
  it('deletePart DELETE /parts/{id}', async () => {
    await deletePart('p1')
    expect(del).toHaveBeenCalledWith('/parts/p1')
  })

  // part categories
  it('listPartCategories GET /part-categories', async () => {
    await listPartCategories()
    expect(get).toHaveBeenCalledWith('/part-categories')
  })
  it('createPartCategory POST /part-categories', async () => {
    await createPartCategory({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/part-categories', { name: 'C' })
  })
  it('updatePartCategory PATCH /part-categories/{id}', async () => {
    await updatePartCategory('c1', { name: 'C2' })
    expect(patch).toHaveBeenCalledWith('/part-categories/c1', { name: 'C2' })
  })
  it('deletePartCategory DELETE /part-categories/{id}', async () => {
    await deletePartCategory('c1')
    expect(del).toHaveBeenCalledWith('/part-categories/c1')
  })

  // purchase orders
  it('listPurchaseOrders GET /purchase-orders (no params)', async () => {
    await listPurchaseOrders()
    expect(get).toHaveBeenCalledWith('/purchase-orders', { params: {} })
  })
  it('listPurchaseOrders GET /purchase-orders with filters', async () => {
    await listPurchaseOrders({ status: 'DRAFT', vendor_id: 'v1' })
    expect(get).toHaveBeenCalledWith('/purchase-orders', {
      params: { status: 'DRAFT', vendor_id: 'v1' },
    })
  })
  it('getPurchaseOrder GET /purchase-orders/{id}', async () => {
    await getPurchaseOrder('po1')
    expect(get).toHaveBeenCalledWith('/purchase-orders/po1')
  })
  it('createPurchaseOrder POST /purchase-orders', async () => {
    await createPurchaseOrder({ vendor_id: 'v1', lines: [] })
    expect(post).toHaveBeenCalledWith('/purchase-orders', { vendor_id: 'v1', lines: [] })
  })
  it('updatePurchaseOrder PATCH /purchase-orders/{id}', async () => {
    await updatePurchaseOrder('po1', { notes: 'x' })
    expect(patch).toHaveBeenCalledWith('/purchase-orders/po1', { notes: 'x' })
  })
  it('deletePurchaseOrder DELETE /purchase-orders/{id}', async () => {
    await deletePurchaseOrder('po1')
    expect(del).toHaveBeenCalledWith('/purchase-orders/po1')
  })
  it('submitPurchaseOrder POST /submit', async () => {
    await submitPurchaseOrder('po1')
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/submit')
  })
  it('approvePurchaseOrder POST /approve with note', async () => {
    await approvePurchaseOrder('po1', { note: 'ok' })
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/approve', { note: 'ok' })
  })
  it('rejectPurchaseOrder POST /reject', async () => {
    await rejectPurchaseOrder('po1', { note: 'no' })
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/reject', { note: 'no' })
  })
  it('cancelPurchaseOrder POST /cancel', async () => {
    await cancelPurchaseOrder('po1', { note: '' })
    expect(post).toHaveBeenCalledWith('/purchase-orders/po1/cancel', { note: '' })
  })
  it('listPurchaseOrderActivities GET /activities', async () => {
    await listPurchaseOrderActivities('po1')
    expect(get).toHaveBeenCalledWith('/purchase-orders/po1/activities')
  })

  // purchase order categories
  it('listPurchaseOrderCategories GET /purchase-order-categories', async () => {
    await listPurchaseOrderCategories()
    expect(get).toHaveBeenCalledWith('/purchase-order-categories')
  })
  it('createPurchaseOrderCategory POST', async () => {
    await createPurchaseOrderCategory({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/purchase-order-categories', { name: 'C' })
  })
  it('updatePurchaseOrderCategory PATCH /{id}', async () => {
    await updatePurchaseOrderCategory('c1', { name: 'C2' })
    expect(patch).toHaveBeenCalledWith('/purchase-order-categories/c1', { name: 'C2' })
  })
  it('deletePurchaseOrderCategory DELETE /{id}', async () => {
    await deletePurchaseOrderCategory('c1')
    expect(del).toHaveBeenCalledWith('/purchase-order-categories/c1')
  })

  // vendors
  it('listVendors GET /vendors', async () => {
    await listVendors()
    expect(get).toHaveBeenCalledWith('/vendors')
  })
  it('listVendorsMini GET /vendors/mini', async () => {
    await listVendorsMini()
    expect(get).toHaveBeenCalledWith('/vendors/mini')
  })
  it('createVendor POST /vendors', async () => {
    await createVendor({ name: 'V' })
    expect(post).toHaveBeenCalledWith('/vendors', { name: 'V' })
  })
  it('updateVendor PATCH /vendors/{id}', async () => {
    await updateVendor('v1', { phone: '1' })
    expect(patch).toHaveBeenCalledWith('/vendors/v1', { phone: '1' })
  })
  it('deleteVendor DELETE /vendors/{id}', async () => {
    await deleteVendor('v1')
    expect(del).toHaveBeenCalledWith('/vendors/v1')
  })

  // customers
  it('listCustomers GET /customers', async () => {
    await listCustomers()
    expect(get).toHaveBeenCalledWith('/customers')
  })
  it('listCustomersMini GET /customers/mini', async () => {
    await listCustomersMini()
    expect(get).toHaveBeenCalledWith('/customers/mini')
  })
  it('createCustomer POST /customers', async () => {
    await createCustomer({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/customers', { name: 'C' })
  })
  it('updateCustomer PATCH /customers/{id}', async () => {
    await updateCustomer('c1', { billing_currency: 'CNY' })
    expect(patch).toHaveBeenCalledWith('/customers/c1', { billing_currency: 'CNY' })
  })
  it('deleteCustomer DELETE /customers/{id}', async () => {
    await deleteCustomer('c1')
    expect(del).toHaveBeenCalledWith('/customers/c1')
  })
})
