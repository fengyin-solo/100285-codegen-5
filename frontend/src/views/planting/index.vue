<template>
  <section class="page" data-module="planting">
    <header class="page-head">
      <div>
        <h2>义务植树发苗</h2>
        <p class="page-desc">
          发苗权限按点位定死：只有本点位归属登记员能录发放，同点位登记冲突以归属登记员为准；
          苗木管理员可退回并写明缘由，其他岗位仅可查阅。发放棵数与活动台账逐一对账。
        </p>
      </div>
    </header>

    <!-- 在岗身份：决定本页能点哪些动作；权限最终以后端按点位判定为准 -->
    <div class="identity-bar">
      <label class="filter-item">
        <span>当前在岗人员（工号）</span>
        <select v-model="operatorCode" @change="applyIdentity">
          <option v-for="p in persons" :key="p.工号" :value="p.工号">
            {{ p.工号 }} · {{ p.姓名 }} · {{ p.岗位 }}{{ p.本点位编号 ? `（本点位 ${p.本点位编号}）` : '' }}
          </option>
        </select>
      </label>
      <label class="filter-item">
        <span>当班班次</span>
        <select v-model="shiftCode" @change="applyShift">
          <option value="A">A · 上午班</option>
          <option value="B">B · 下午轮换班</option>
        </select>
      </label>
      <div class="perm-box" :class="permTone">
        <strong>{{ current ? current.姓名 : '未选择' }}（{{ currentRole }}）</strong>
        <span>{{ permissionHint }}</span>
      </div>
    </div>

    <div v-if="feedback" class="feedback" :class="feedback.type">
      <span>{{ feedback.title }}</span>
      <span v-if="feedback.missing" class="missing">缺少权限：{{ feedback.missing }}</span>
    </div>

    <nav class="tabs">
      <button v-for="tab in tabs" :key="tab.key" class="tab" :class="{ active: activeTab === tab.key }"
              type="button" @click="activeTab = tab.key">{{ tab.label }}</button>
    </nav>

    <!-- 发苗登记 -->
    <div v-if="activeTab === 'issue'" class="tab-panel">
      <form class="form-card" @submit.prevent="submitIssue">
        <label class="filter-item">
          <span>报名表（报名编号）</span>
          <select v-model="form.signupCode" @change="onSignupChange">
            <option value="" disabled>请选择本次要发放的报名表</option>
            <option v-for="l in ledger" :key="l.报名编号" :value="l.报名编号">
              {{ l.报名编号 }} · {{ l.点位编号 }} {{ l.点位名称 }} · {{ l.报名单位 }} · 台账应发 {{ l.应发棵数 }} 棵
            </option>
          </select>
        </label>
        <label class="filter-item">
          <span>实发棵数</span>
          <input v-model.number="form.quantity" type="number" min="0" placeholder="须与台账应发一致" />
        </label>
        <button class="btn primary" type="submit">登记发放</button>
      </form>

      <div v-if="selectedLedger" class="ledger-preview">
        <p>点位：<strong>{{ selectedLedger.点位编号 }} {{ selectedLedger.点位名称 }}</strong>
           · 树种 {{ selectedLedger.树种 }} · 活动台账应发 <strong>{{ selectedLedger.应发棵数 }}</strong> 棵</p>
        <p v-if="current && current.岗位 === '登记员' && current.本点位编号 !== selectedLedger.点位编号"
           class="warn-text">
          你归属 {{ current.本点位编号 || '无固定点位' }} 点位，不是 {{ selectedLedger.点位编号 }}
          的本点位登记员，提交将被当场驳回。
        </p>
        <p v-if="current && current.岗位 !== '登记员'" class="warn-text">
          你的岗位是 {{ current.岗位 }}，对发放记录只能查阅，登记将被驳回。
        </p>
      </div>
    </div>

    <!-- 发放记录 -->
    <div v-if="activeTab === 'records'" class="tab-panel">
      <form class="filter-bar" @submit.prevent="loadIssues">
        <label class="filter-item">
          <span>点位</span>
          <select v-model="issueFilter.station_code">
            <option value="">全部点位</option>
            <option v-for="s in stations" :key="s.点位编号" :value="s.点位编号">{{ s.点位编号 }} {{ s.点位名称 }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>状态</span>
          <select v-model="issueFilter.status">
            <option value="">全部状态</option>
            <option value="已发放">已发放</option>
            <option value="已退回">已退回</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetIssueFilter">重置</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>报名编号</th><th>点位</th><th>报名单位</th><th>树种</th><th>发放棵数</th>
            <th>状态</th><th>原登记人</th><th>发放时间</th><th>退回信息</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in issues" :key="String(row.id)">
            <td>{{ row.报名编号 }}</td>
            <td>{{ row.点位编号 }} {{ row.点位名称 }}</td>
            <td>{{ row.报名单位 }}</td>
            <td>{{ row.树种 }}</td>
            <td>{{ row.发放棵数 }}</td>
            <td><span class="badge" :class="row.状态 === '已退回' ? 'bad' : 'ok'">{{ row.状态 }}</span></td>
            <td>{{ row.登记人姓名 }}<span v-if="row.班次" class="sub">（{{ row.班次 }} 班）</span></td>
            <td>{{ row.发放时间 }}</td>
            <td>
              <template v-if="row.状态 === '已退回'">
                <div>{{ row.退回人姓名 }} · {{ row.退回时间 }}</div>
                <div class="sub">缘由：{{ row.退回缘由 }}</div>
              </template>
              <span v-else class="sub">—</span>
            </td>
            <td class="row-actions">
              <button v-if="row.状态 === '已发放' && isNursery" class="link" type="button"
                      @click="openReturn(row)">退回</button>
              <span v-else-if="row.状态 === '已发放'" class="sub">仅可查阅</span>
              <span v-else class="sub">已退回</span>
            </td>
          </tr>
          <tr v-if="!issues.length">
            <td colspan="10" class="empty-state">当前条件下暂无发放记录</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>共 {{ issueTotal }} 条发放记录（任何岗位均可查阅）</span></footer>
    </div>

    <!-- 发放汇总对账 -->
    <div v-if="activeTab === 'summary'" class="tab-panel">
      <form class="filter-bar" @submit.prevent="loadSummary">
        <label class="filter-item">
          <span>点位</span>
          <select v-model="summaryStation">
            <option value="">全部点位</option>
            <option v-for="s in stations" :key="s.点位编号" :value="s.点位编号">{{ s.点位编号 }} {{ s.点位名称 }}</option>
          </select>
        </label>
        <button class="btn" type="submit">对账</button>
      </form>

      <div class="stat-row">
        <article v-for="card in summaryCards" :key="card.label" class="stat-card">
          <span class="stat-label">{{ card.label }}</span>
          <strong class="stat-value">{{ card.value }}</strong>
        </article>
      </div>

      <div class="feedback" :class="summary && summary.consistent ? 'ok' : 'error'">
        <span v-if="summary && summary.consistent">
          对账已平：{{ summary.equation }}（{{ summary.totals.台账应发 }} 棵，全部与活动台账相符）
        </span>
        <span v-else>对账不平，请核对下列明细</span>
        <ul v-if="summary && summary.checks.length" class="check-list">
          <li v-for="(c, i) in summary.checks" :key="i">{{ c }}</li>
        </ul>
      </div>

      <h3 class="block-title">按点位汇总</h3>
      <table class="data-table">
        <thead>
          <tr><th>点位</th><th>报名单位数</th><th>台账应发</th><th>净发放</th><th>已退回</th><th>未发放</th></tr>
        </thead>
        <tbody>
          <tr v-for="s in summary?.by_station ?? []" :key="s.点位编号">
            <td>{{ s.点位编号 }} {{ s.点位名称 }}</td>
            <td>{{ s.报名单位数 }}</td><td>{{ s.台账应发 }}</td><td>{{ s.净发放 }}</td>
            <td>{{ s.已退回 }}</td><td>{{ s.未发放 }}</td>
          </tr>
        </tbody>
      </table>

      <h3 class="block-title">逐报名表明细（含原登记人与退回缘由）</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>报名编号</th><th>点位</th><th>报名单位</th><th>台账应发</th><th>净发放</th>
            <th>已退回</th><th>未发放</th><th>状态</th><th>原登记人</th><th>退回缘由</th><th>对账</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in summary?.items ?? []" :key="d.报名编号">
            <td>{{ d.报名编号 }}</td><td>{{ d.点位编号 }}</td><td>{{ d.报名单位 }}</td>
            <td>{{ d.台账应发 }}</td><td>{{ d.净发放 }}</td><td>{{ d.已退回 }}</td><td>{{ d.未发放 }}</td>
            <td>{{ d.状态 }}</td><td>{{ d.原登记人 ?? '—' }}</td>
            <td>{{ d.退回缘由 ?? '—' }}</td>
            <td><span class="badge" :class="d.对账 === '平' ? 'ok' : 'bad'">{{ d.对账 }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 点位与排班 -->
    <div v-if="activeTab === 'stations'" class="tab-panel">
      <h3 class="block-title">点位归属登记员（发苗权限只认此人）</h3>
      <table class="data-table">
        <thead><tr><th>点位编号</th><th>点位名称</th><th>归属登记员工号</th><th>归属登记员</th></tr></thead>
        <tbody>
          <tr v-for="s in stations" :key="s.点位编号">
            <td>{{ s.点位编号 }}</td><td>{{ s.点位名称 }}</td>
            <td>{{ s.归属登记员工号 }}</td><td><strong>{{ s.归属登记员姓名 }}</strong></td>
          </tr>
        </tbody>
      </table>

      <h3 class="block-title">当天排班与人员轮换（顶班 ≠ 归属，顶班人无该点位发放权）</h3>
      <table class="data-table">
        <thead>
          <tr><th>班次</th><th>点位</th><th>当班登记员</th><th>是否本点位归属</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in roster" :key="`${r.班次}-${r.点位编号}`">
            <td>{{ r.班次 }} · {{ r.班次名称 }}</td>
            <td>{{ r.点位编号 }} {{ r.点位名称 }}</td>
            <td>{{ r.登记员姓名 }}（{{ r.登记员工号 }}）</td>
            <td>
              <span class="badge" :class="r.是否归属登记员 ? 'ok' : 'warn'">
                {{ r.是否归属登记员 ? '归属登记员' : '轮换顶班' }}
              </span>
            </td>
            <td class="sub">{{ r.备注 }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 退回弹窗：苗木管理员须写明缘由 -->
    <div v-if="returnTarget" class="modal-mask" @click.self="returnTarget = null">
      <div class="modal">
        <h3>退回发放记录 #{{ returnTarget.id }}</h3>
        <p class="sub">
          {{ returnTarget.报名编号 }} · {{ returnTarget.点位编号 }} · {{ returnTarget.发放棵数 }} 棵 ·
          原登记人 {{ returnTarget.登记人姓名 }}
        </p>
        <label class="filter-item">
          <span>退回缘由（必填）</span>
          <textarea v-model="returnReason" rows="3" placeholder="如：树苗根系受损，无法栽植，退回重领"></textarea>
        </label>
        <div class="modal-actions">
          <button class="btn" type="button" @click="returnTarget = null">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitReturn">确认退回</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

type Person = { id: number; 工号: string; 姓名: string; 岗位: string; 本点位编号: string | null }
type Station = { 点位编号: string; 点位名称: string; 归属登记员工号: string; 归属登记员姓名: string }
type RosterRow = {
  班次: string; 班次名称: string; 点位编号: string; 点位名称: string
  登记员工号: string; 登记员姓名: string; 是否归属登记员: boolean; 备注: string
}
type LedgerRow = { 报名编号: string; 点位编号: string; 点位名称: string; 报名单位: string; 树种: string; 应发棵数: number }
type Feedback = { type: 'ok' | 'error'; title: string; missing?: string }

const tabs = [
  { key: 'issue', label: '发苗登记' },
  { key: 'records', label: '发放记录' },
  { key: 'summary', label: '发放汇总对账' },
  { key: 'stations', label: '点位与排班' },
] as const

const activeTab = ref<(typeof tabs)[number]['key']>('issue')
const feedback = ref<Feedback | null>(null)
let feedbackTimer: ReturnType<typeof setTimeout> | undefined

function notify(type: Feedback['type'], title: string, missing?: string) {
  feedback.value = { type, title, missing }
  clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => (feedback.value = null), 6000)
}

const persons = ref<Person[]>([])
const stations = ref<Station[]>([])
const roster = ref<RosterRow[]>([])
const ledger = ref<LedgerRow[]>([])
const operatorCode = ref('')
const shiftCode = ref('A')

const current = computed(() => persons.value.find((p) => p.工号 === operatorCode.value) ?? null)
const currentRole = computed(() => current.value?.岗位 ?? '')
const isNursery = computed(() => store.isNursery)

const stationNameOf = (code: string | null | undefined) =>
  stations.value.find((s) => s.点位编号 === code)?.点位名称 ?? ''

const permissionHint = computed(() => {
  const p = current.value
  if (!p) return '请先选择在岗人员'
  if (p.岗位 === '登记员') {
    return p.本点位编号
      ? `可在本点位 ${p.本点位编号}（${stationNameOf(p.本点位编号)}）登记发放；替别的点位或非归属登记将被当场驳回。`
      : '登记员未绑定归属点位，不能登记发放。'
  }
  if (p.岗位 === '苗木管理员') return '可退回已发放记录并写明缘由；不能登记发放。'
  return '对发放记录仅可查阅，不能登记发放或退回。'
})
const permTone = computed(() => {
  const role = current.value?.岗位
  if (role === '登记员') return 'tone-registrar'
  if (role === '苗木管理员') return 'tone-nursery'
  return 'tone-readonly'
})

function applyIdentity() {
  const p = current.value
  if (!p) return
  store.setIdentity(p, stationNameOf(p.本点位编号))
  store.setShiftCode(shiftCode.value, `${shiftCode.value} 班`)
}
function applyShift() {
  store.shift = shiftCode.value
}

// ---------- 发苗登记 ----------
const form = ref<{ signupCode: string; quantity: number | null }>({ signupCode: '', quantity: null })
const selectedLedger = computed(() => ledger.value.find((l) => l.报名编号 === form.value.signupCode) ?? null)

function onSignupChange() {
  if (selectedLedger.value) form.value.quantity = selectedLedger.value.应发棵数
}

async function submitIssue() {
  if (!form.value.signupCode) {
    notify('error', '请先选择报名表')
    return
  }
  const result = await postJson(
    `/api/planting/issues?operator_code=${encodeURIComponent(operatorCode.value)}&shift=${encodeURIComponent(shiftCode.value)}`,
    { signup_code: form.value.signupCode, quantity: form.value.quantity },
  )
  if (result.ok) {
    notify('ok', result.data.message ?? '发放已登记')
    form.value = { signupCode: '', quantity: null }
    await Promise.all([loadIssues(), loadSummary()])
  } else {
    notify('error', detailMessage(result.data), detailMissing(result.data))
  }
}

// ---------- 发放记录 ----------
const issues = ref<Record<string, any>[]>([])
const issueTotal = ref(0)
const issueFilter = ref<{ station_code: string; status: string }>({ station_code: '', status: '' })

function resetIssueFilter() {
  issueFilter.value = { station_code: '', status: '' }
  void loadIssues()
}

async function loadIssues() {
  const params = new URLSearchParams()
  if (issueFilter.value.station_code) params.set('station_code', issueFilter.value.station_code)
  if (issueFilter.value.status) params.set('status', issueFilter.value.status)
  params.set('size', '200')
  const resp = await request(`/api/planting/issues?${params.toString()}`)
  if (resp.ok) {
    const data = await resp.json()
    issues.value = data.items ?? []
    issueTotal.value = data.total ?? 0
  }
}

// ---------- 退回 ----------
const returnTarget = ref<Record<string, any> | null>(null)
const returnReason = ref('')
const submitting = ref(false)

function openReturn(row: Record<string, any>) {
  returnTarget.value = row
  returnReason.value = ''
}

async function submitReturn() {
  if (!returnTarget.value) return
  if (!returnReason.value.trim()) {
    notify('error', '退回必须写明缘由，不能为空')
    return
  }
  submitting.value = true
  const result = await postJson(
    `/api/planting/issues/${returnTarget.value.id}/return?operator_code=${encodeURIComponent(operatorCode.value)}`,
    { reason: returnReason.value },
  )
  submitting.value = false
  if (result.ok) {
    notify('ok', result.data.message ?? '已退回')
    returnTarget.value = null
    await Promise.all([loadIssues(), loadSummary()])
  } else {
    notify('error', detailMessage(result.data), detailMissing(result.data))
  }
}

// ---------- 汇总 ----------
type Summary = {
  totals: Record<string, number>
  by_station: Record<string, any>[]
  equation: string
  equation_ok: boolean
  consistent: boolean
  checks: string[]
  items: Record<string, any>[]
}
const summary = ref<Summary | null>(null)
const summaryStation = ref('')

const summaryCards = computed(() => {
  const t = summary.value?.totals
  return [
    { label: '报名单位数', value: t?.['报名单位数'] ?? 0 },
    { label: '台账应发（棵）', value: t?.['台账应发'] ?? 0 },
    { label: '净发放（棵）', value: t?.['净发放'] ?? 0 },
    { label: '已退回（棵）', value: t?.['已退回'] ?? 0 },
    { label: '未发放（棵）', value: t?.['未发放'] ?? 0 },
  ]
})

async function loadSummary() {
  const qs = summaryStation.value ? `?station_code=${encodeURIComponent(summaryStation.value)}` : ''
  const resp = await request(`/api/planting/summary${qs}`)
  if (resp.ok) summary.value = await resp.json()
}

// ---------- 通用 ----------
async function getJson<T>(path: string): Promise<T | null> {
  const resp = await request(path)
  return resp.ok ? ((await resp.json()) as T) : null
}

async function postJson(path: string, body: unknown) {
  const resp = await request(path, { method: 'POST', body: JSON.stringify(body) })
  const data = await resp.json().catch(() => ({}))
  return { ok: resp.ok, status: resp.status, data }
}

function detailMessage(data: any): string {
  return data?.detail?.message ?? data?.message ?? '操作未生效，请稍后重试'
}
function detailMissing(data: any): string | undefined {
  return data?.detail?.missing_permission
}

onMounted(async () => {
  const [personData, stationData, rosterData, ledgerData] = await Promise.all([
    getJson<{ items: Person[] }>('/api/planting/persons'),
    getJson<{ items: Station[] }>('/api/planting/stations'),
    getJson<{ items: RosterRow[] }>('/api/planting/roster'),
    getJson<{ items: LedgerRow[] }>('/api/planting/ledger'),
  ])
  persons.value = personData?.items ?? []
  stations.value = stationData?.items ?? []
  roster.value = rosterData?.items ?? []
  ledger.value = ledgerData?.items ?? []
  operatorCode.value = persons.value[0]?.工号 ?? ''
  applyIdentity()
  await Promise.all([loadIssues(), loadSummary()])
})
</script>
