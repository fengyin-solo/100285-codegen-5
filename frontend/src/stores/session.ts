import { defineStore } from 'pinia'

interface OperatorInfo {
  staff_id: number
  姓名: string
  岗位: string
  所属点位: string
  permissions: string[]
}

export const PERM_ISSUE = '发苗登记：本点位现任登记员'
export const PERM_RETURN = '发苗退回：苗木管理员'

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '园林绿化养护管理平台',
    /** 义务植树发苗：当前登录人员工号（X-Staff-Id），0 表示未选择。 */
    staffId: 0,
    operatorInfo: null as OperatorInfo | null,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    permissions: (state) => state.operatorInfo?.permissions ?? ['发苗查阅：全部岗位'],
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setStaff(staffId: number, info: OperatorInfo | null) {
      this.staffId = staffId
      this.operatorInfo = info
      this.operator = info ? `${info.姓名}（${info.岗位}${info.所属点位 ? ' · ' + info.所属点位 : ''}）` : '未选择人员'
    },
    can(code: string): boolean {
      return this.permissions.includes(code)
    },
  },
})
