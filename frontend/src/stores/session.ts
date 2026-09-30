import { defineStore } from 'pinia'

export type RoleName = '登记员' | '苗木管理员' | '志愿者' | ''

export const useSessionStore = defineStore('session', {
  state: () => ({
    // 兼容既有页头：未选择发苗身份前仍显示默认值班人
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '园林绿化养护管理平台',
    // 义务植树发苗身份：工号、岗位、归属点位（轮换后归属不变）
    operatorCode: '',
    role: '' as RoleName,
    homeStation: '',
    stationName: '',
    shift: '',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    isRegistrar: (state) => state.role === '登记员',
    isNursery: (state) => state.role === '苗木管理员',
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    /** 选择当前在岗人员，页头同步显示其姓名、岗位与本点位。 */
    setIdentity(person: {
      工号: string
      姓名: string
      岗位: string
      本点位编号: string | null
    }, stationName?: string) {
      this.operatorCode = person.工号
      this.operator = person.姓名
      this.role = person.岗位 as RoleName
      this.homeStation = person.本点位编号 ?? ''
      this.stationName = stationName ?? ''
      this.shift = ''
      this.shiftLabel = this.homeStation
        ? `${person.岗位} · 归属点位 ${this.homeStation}${stationName ? ` ${stationName}` : ''}`
        : `${person.岗位} · 全局（无固定点位）`
    },
    setShiftCode(shift: string, label?: string) {
      this.shift = shift
      if (label) this.shiftLabel = label
    },
  },
})
