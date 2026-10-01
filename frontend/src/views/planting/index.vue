<template>
  <section class="page" data-module="planting">
    <header class="page-head">
      <div>
        <h2>义务植树发苗</h2>
        <p class="page-desc">发苗权限按点位定死：只有本点位现任登记员能录发放；苗木管理员可退回并写明缘由；其他岗位只能查阅。</p>
      </div>
    </header>

    <!-- 当前身份：当天发苗现场靠它区分谁能做什么 -->
    <div class="identity-bar">
      <label class="identity-pick">
        <span>当前登录人员</span>
        <select :value="session.staffId" @change="switchStaff(Number(($event.target as HTMLSelectElement).value))">
          <option :value="0">未选择（无任何操作权限）</option>
          <option v-for="s in staff" :key="s.id" :value="s.id">
            {{ s.姓名 }} · {{ s.岗位 }}{{ s.所属点位 ? ' · ' + s.所属点位 : '' }}{{ s.在职 ? '' : '（已离岗）' }}
          </option>
        </select>
      </label>
      <div v-if="session.operatorInfo" class="identity-meta">
        <span class="tag" v-for="p in session.permissions" :key="p">{{ p }}</span>
      </div>
    </div>

    <div v-if="flash" class="flash" :class="flashOk ? 'flash-ok' : 'flash-bad'">{{ flash }}</div>

    <div class="tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="tab"
        :class="{ active: tab === t.key }"
        type="button"
        @click="tab = t.key"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- 报名表：发放入口 -->
    <div v-if="tab === 'signups'">
      <form class="filter-bar" @submit.prevent="reloadSignups">
        <label class="filter-item">
          <span>点位</span>
          <select v-model="pointFilter">
            <option value="">全部点位</option>
            <option v-for="p in points" :key="p.点位编号" :value="p.点位编号">{{ p.点位名称 }}（{{ p.点位编号 }}）</option>
          </select>
        </label>
        <label class="filter-item">
          <span>报名状态</span>
          <select v-model="statusFilter">
            <option value="">全部</option>
            <option>待发放</option>
            <option>已发放</option>
            <option>已退回</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>报名编号</th><th>点位</th><th>报名人</th><th>树种</th><th>拟领棵数</th><th>状态</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in signups" :key="row.报名编号">
            <td>{{ row.报名编号 }}</td>
            <td>{{ pointName(row.点位编号) }}</td>
            <td>{{ row.报名人 }}</td>
            <td>{{ row.树种 }}</td>
            <td>{{ row.拟领棵数 }}</td>
            <td>
              <span class="state" :class="stateClass(row.状态)">{{ row.状态 }}</span>
            </td>
            <td>
              <button
                v-if="row.状态 === '待发放'"
                class="link"
                type="button"
                :disabled="!canIssue"
                :title="canIssue ? '' : '缺少权限：发苗登记 · 本点位现任登记员'"
                @click="issue(row)"
              >
                发放
              </button>
              <span v-else class="muted">—</span>
            </td>
          </tr>
          <tr v-if="!signups.length"><td colspan="7" class="empty-state">没有符合条件的报名表</td></tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>共 {{ signups.length }} 份报名表；发放按钮只对本点位现任登记员可用。</span></footer>
    </div>

    <!-- 发放记录：谁领了几棵、谁登记、谁退回 -->
    <div v-if="tab === 'issues'">
      <table class="data-table">
        <thead>
          <tr>
            <th>报名编号</th><th>点位</th><th>报名人</th><th>树种</th><th>发放棵数</th>
            <th>原登记人</th><th>发放时间</th><th>状态</th><th>退回缘由 / 退回人</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in issues" :key="row.id">
            <td>{{ row.报名编号 }}</td>
            <td>{{ row.点位名称 }}（{{ row.点位编号 }}）</td>
            <td>{{ row.报名人 }}</td>
            <td>{{ row.树种 }}</td>
            <td><strong>{{ row.发放棵数 }}</strong></td>
            <td>{{ row.登记人姓名 }}<span v-if="row.登记人姓名 !== currentName(row.点位编号)" class="muted">（原登记人）</span></td>
            <td>{{ row.发放时间 }}</td>
            <td><span class="state" :class="stateClass(row.状态)">{{ row.状态 }}</span></td>
            <td>
              <template v-if="row.状态 === '已退回'">
                {{ row.退回缘由 }}<span class="muted"> — {{ row.退回人 }} {{ row.退回时间 }}</span>
              </template>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <button
                v-if="row.状态 === '已发放'"
                class="link danger"
                type="button"
                :disabled="!canReturn"
                :title="canReturn ? '' : '缺少权限：发苗退回（苗木管理员）'"
                @click="askReturn(row)"
              >
                退回
              </button>
              <span v-else class="muted">—</span>
            </td>
          </tr>
          <tr v-if="!issues.length"><td colspan="10" class="empty-state">暂无发放记录</td></tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>所有岗位均可查阅本页；仅{{ '苗木管理员' }}能执行退回，且缘由必填。</span></footer>
    </div>

    <!-- 汇总对账 -->
    <div v-if="tab === 'summary' && summary">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">对账结论</span>
          <strong class="stat-value" :class="summary.reconciled ? 'ok-text' : 'bad-text'">
            {{ summary.reconciled ? '账实一致' : '存在差异' }}
          </strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">有效发放记录</span>
          <strong class="stat-value">{{ summary.issue_count }}</strong>
        </article>
      </div>

      <h3>按点位汇总（与活动台账逐行对账）</h3>
      <table class="data-table">
        <thead>
          <tr><th>点位</th><th>现任登记员</th><th>计划合计</th><th>已发合计</th><th>尚缺苗数</th><th>对账</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in summary.points" :key="p.点位编号">
            <td>{{ p.点位名称 }}（{{ p.点位编号 }}）</td>
            <td>{{ p.现任登记员 }}</td>
            <td>{{ p.计划合计 }}</td>
            <td>{{ p.已发合计 }}</td>
            <td :class="p.缺苗数 > 0 ? 'bad-text' : ''">{{ p.缺苗数 }}</td>
            <td>
              <span class="state" :class="p.对账一致 ? 'state-ok' : 'state-bad'">
                {{ p.对账一致 ? '一致' : '不一致' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <h3>活动台账逐行明细</h3>
      <table class="data-table">
        <thead>
          <tr><th>点位</th><th>树种</th><th>计划苗数</th><th>台账已发</th><th>发放汇总</th><th>剩余</th><th>对账</th></tr>
        </thead>
        <tbody>
          <tr v-for="line in summary.ledger_lines" :key="line.点位编号 + line.树种">
            <td>{{ line.点位名称 }}</td>
            <td>{{ line.树种 }}</td>
            <td>{{ line.计划苗数 }}</td>
            <td>{{ line.台账已发苗数 }}</td>
            <td>{{ line.汇总已发苗数 }}</td>
            <td>{{ line.剩余苗数 }}</td>
            <td>
              <span class="state" :class="line.对账一致 ? 'state-ok' : 'state-bad'">
                {{ line.对账一致 ? '一致' : '不一致' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>{{ summary.message }}</span></footer>
    </div>

    <!-- 点位与人员轮换 -->
    <div v-if="tab === 'points'">
      <table class="data-table">
        <thead>
          <tr><th>点位编号</th><th>点位名称</th><th>现任登记员</th><th>人员轮换</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in points" :key="p.点位编号">
            <td>{{ p.点位编号 }}</td>
            <td>{{ p.点位名称 }}</td>
            <td>{{ p.现任登记员姓名 }}</td>
            <td class="row-actions">
              <select v-model="rotatePick[p.点位编号]">
                <option value="">选择登记员…</option>
                <option
                  v-for="s in registrarChoices(p.点位编号)"
                  :key="s.id"
                  :value="s.id"
                >
                  {{ s.姓名 }}{{ s.id === p.现任登记员ID ? '（现任）' : s.在职 ? '（协助）' : '（已轮换离岗）' }}
                </option>
              </select>
              <button class="btn" type="button" @click="rotate(p)">轮换为所选登记员</button>
            </td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>轮换只改点位现任登记员；历史发放记录始终标出原登记人，不随轮换改名。</span></footer>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { PERM_ISSUE, PERM_RETURN, useSessionStore } from '@/stores/session'

type Staff = {
  id: number
  姓名: string
  岗位: string
  所属点位: string
  在职: boolean
  说明: string
}
type Point = { id: number; 点位编号: string; 点位名称: string; 现任登记员ID: number; 现任登记员姓名: string }
type Signup = { 报名编号: string; 点位编号: string; 报名人: string; 树种: string; 拟领棵数: number; 状态: string }
type Issue = {
  id: number
  报名编号: string
  点位编号: string
  点位名称: string
  报名人: string
  树种: string
  发放棵数: number
  登记人ID: number
  登记人姓名: string
  发放时间: string
  状态: string
  退回缘由: string
  退回人: string
  退回时间: string
}
type Summary = {
  reconciled: boolean
  message: string
  issue_count: number
  points: Array<{ 点位编号: string; 点位名称: string; 现任登记员: string; 计划合计: number; 已发合计: number; 缺苗数: number; 对账一致: boolean }>
  ledger_lines: Array<{ 点位编号: string; 点位名称: string; 树种: string; 计划苗数: number; 台账已发苗数: number; 汇总已发苗数: number; 剩余苗数: number; 对账一致: boolean }>
}

const ENDPOINT = '/api/planting'
const session = useSessionStore()

const tabs = [
  { key: 'signups', label: '报名表与发放' },
  { key: 'issues', label: '发放记录' },
  { key: 'summary', label: '发放汇总对账' },
  { key: 'points', label: '点位与轮换' },
]
const tab = ref('signups')

const staff = ref<Staff[]>([])
const points = ref<Point[]>([])
const signups = ref<Signup[]>([])
const issues = ref<Issue[]>([])
const summary = ref<Summary | null>(null)
const pointFilter = ref('')
const statusFilter = ref('')
const rotatePick = reactive<Record<string, number>>({})

const flash = ref('')
const flashOk = ref(true)
function notify(message: string, ok = false) {
  flash.value = message
  flashOk.value = ok
}

const canIssue = computed(() => session.can(PERM_ISSUE))
const canReturn = computed(() => session.can(PERM_RETURN))

function pointName(code: string) {
  return points.value.find((p) => p.点位编号 === code)?.点位名称 ?? code
}
function currentName(code: string) {
  return points.value.find((p) => p.点位编号 === code)?.现任登记员姓名 ?? ''
}
function registrarChoices(code: string) {
  return staff.value.filter((s) => s.岗位 === '点位登记员' && (s.所属点位 === code || s.所属点位 === ''))
}
function stateClass(state: string) {
  if (state === '已发放') return 'state-ok'
  if (state === '已退回') return 'state-bad'
  return 'state-pending'
}

async function postJson(path: string, body: unknown): Promise<{ ok: boolean; message: string; entry: Record<string, unknown> | null }> {
  const resp = await request(`${ENDPOINT}${path}`, { method: 'POST', body: JSON.stringify(body) })
  return resp.json()
}

async function loadMe() {
  const resp = await request(`${ENDPOINT}/me`)
  const info = await resp.json()
  session.setStaff(session.staffId, info.姓名 === '未知人员' ? null : info)
}

async function switchStaff(id: number) {
  session.setStaff(id, null)
  localStorage.setItem('planting-staff-id', String(id))
  if (id) {
    const resp = await request(`${ENDPOINT}/me`, { headers: { 'X-Staff-Id': String(id) } })
    const info = await resp.json()
    session.setStaff(id, info.姓名 === '未知人员' ? null : info)
  }
  notify(`已切换为：${session.operator}（权限：${session.permissions.join('、')}）`, true)
}

async function reloadBase() {
  const [s, p] = await Promise.all([
    request(`${ENDPOINT}/staff`).then((r) => r.json()),
    request(`${ENDPOINT}/points`).then((r) => r.json()),
  ])
  staff.value = s.items
  points.value = p.items
}

async function reloadSignups() {
  const qs = new URLSearchParams()
  if (pointFilter.value) qs.set('point_code', pointFilter.value)
  if (statusFilter.value) qs.set('status', statusFilter.value)
  const resp = await request(`${ENDPOINT}/signups?${qs.toString()}`)
  const data = await resp.json()
  signups.value = data.items
}

async function reloadIssues() {
  const resp = await request(`${ENDPOINT}/issues`)
  const data = await resp.json()
  issues.value = data.items
}

async function reloadSummary() {
  const resp = await request(`${ENDPOINT}/summary`)
  summary.value = await resp.json()
}

async function issue(row: Signup) {
  if (!canIssue.value) {
    notify(`当场驳回：缺少权限「${PERM_ISSUE} · ${pointName(row.点位编号)}」。`, false)
    return
  }
  const r = await postJson('/issues', { signup_no: row.报名编号, count: row.拟领棵数 })
  notify(r.message, r.ok)
  if (r.ok) await Promise.all([reloadSignups(), reloadSummarySafe()])
}

async function askReturn(row: Issue) {
  if (!canReturn.value) {
    notify(`当场驳回：缺少权限「${PERM_RETURN}」，只有苗木管理员可以退回。`, false)
    return
  }
  const reason = window.prompt(`退回报名表 ${row.报名编号}（${row.报名人} ${row.发放棵数}棵${row.树种}）的发放，请写明缘由：`)
  if (reason === null) return
  const r = await postJson(`/issues/${row.id}/return`, { reason })
  notify(r.message, r.ok)
  if (r.ok) await Promise.all([reloadIssues(), reloadSignups(), reloadSummarySafe()])
}

async function rotate(p: Point) {
  const newId = Number(rotatePick[p.点位编号])
  if (!newId) {
    notify('请先选择要接任的登记员。', false)
    return
  }
  const r = await postJson('/rotate', { point_code: p.点位编号, new_staff_id: newId })
  notify(r.message, r.ok)
  if (r.ok) {
    await Promise.all([reloadBase(), reloadIssues()])
    if (session.staffId) await loadMe()
  }
}

async function reloadSummarySafe() {
  if (tab.value === 'summary') await reloadSummary()
}

onMounted(async () => {
  const saved = Number(localStorage.getItem('planting-staff-id') || '0')
  if (saved) session.staffId = saved
  await reloadBase()
  if (saved) await loadMe()
  await Promise.all([reloadSignups(), reloadIssues(), reloadSummary()])
})
</script>

<style scoped>
.identity-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
}
.identity-pick span { display: block; font-size: 12px; color: var(--muted); }
.identity-pick select { min-width: 260px; padding: 4px 8px; }
.identity-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.tag { font-size: 12px; background: #eef4ff; color: #1f6feb; border: 1px solid #c7dbff; border-radius: 999px; padding: 2px 10px; }
.flash { border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; font-size: 13px; white-space: pre-wrap; }
.flash-ok { background: #ecfdf3; border: 1px solid #abefc6; color: #067647; }
.flash-bad { background: #fef3f2; border: 1px solid #fda29b; color: #b42318; }
.tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.tab { border: 1px solid var(--border); background: #fff; border-radius: 6px 6px 0 0; padding: 6px 14px; cursor: pointer; font-size: 13px; }
.tab.active { background: var(--brand); border-color: var(--brand); color: #fff; }
.state { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: 12px; }
.state-ok { background: #ecfdf3; color: #067647; }
.state-bad { background: #fef3f2; color: #b42318; }
.state-pending { background: #fffaeb; color: #b54708; }
.ok-text { color: #067647; }
.bad-text { color: #b42318; }
.muted { color: var(--muted); }
button:disabled { color: #9aa4b2; cursor: not-allowed; text-decoration: none; }
.link.danger { color: #b42318; }
h3 { font-size: 14px; margin: 18px 0 8px; }
</style>
