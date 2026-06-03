import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, put, patch, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, put, patch, delete: del } }))

import { listUsers, inviteUser, updateUser } from '@/api/users'
import { listRoles } from '@/api/roles'
import { setTeamMembers } from '@/api/teams'
import { getCompanySettings, updateCompanySettings } from '@/api/companySettings'
import { listCurrencies } from '@/api/currencies'
import { listPermissions } from '@/api/permissions'

describe('platform api', () => {
  beforeEach(() => {
    for (const m of [get, post, put, patch, del]) m.mockReset().mockResolvedValue({ data: [] })
  })
  it('listUsers GET /users', async () => {
    await listUsers()
    expect(get).toHaveBeenCalledWith('/users')
  })
  it('inviteUser POST /users/invite', async () => {
    await inviteUser({ email: 'x@y.com', role_id: 'r1' })
    expect(post).toHaveBeenCalledWith('/users/invite', { email: 'x@y.com', role_id: 'r1' })
  })
  it('updateUser PATCH /users/{id}', async () => {
    await updateUser('u1', { status: 'inactive' })
    expect(patch).toHaveBeenCalledWith('/users/u1', { status: 'inactive' })
  })
  it('listRoles GET /roles', async () => {
    await listRoles()
    expect(get).toHaveBeenCalledWith('/roles')
  })
  it('setTeamMembers PUT /teams/{id}/members', async () => {
    await setTeamMembers('t1', ['u1'])
    expect(put).toHaveBeenCalledWith('/teams/t1/members', { user_ids: ['u1'] })
  })
  it('getCompanySettings GET /company-settings', async () => {
    await getCompanySettings()
    expect(get).toHaveBeenCalledWith('/company-settings')
  })
  it('updateCompanySettings PUT /company-settings', async () => {
    await updateCompanySettings({ auto_assign: true })
    expect(put).toHaveBeenCalledWith('/company-settings', { auto_assign: true })
  })
  it('listCurrencies GET /currencies', async () => {
    await listCurrencies()
    expect(get).toHaveBeenCalledWith('/currencies')
  })
  it('listPermissions GET /permissions', async () => {
    await listPermissions()
    expect(get).toHaveBeenCalledWith('/permissions')
  })
})
