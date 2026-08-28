/* 左辅云创 · 管理后台 H5（阶段五 T5-1~T5-4 / T5-6 / T5-7；台账对账依赖阶段四暂不可用） */
const API = '/api'
const TOKEN_KEY = 'zf_admin_token'
let currentPage = 'users'

/* ---------------- 工具 ---------------- */
const $ = (sel) => document.querySelector(sel)

function esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const APPROVAL_LABEL = { pending: '待审批', approved: '已通过', rejected: '已驳回' }
const STATUS_LABEL = { active: '正常', blocked: '已封禁' }
const TYPE_LABEL = { alter_original: '改动原图', edit_jitter: '抖动', submit_irrelevant: '乱传无关图', other: '其他' }
const PUNISH_LABEL = { warning: '警告', suspend: '停权', block: '封禁' }
const ANNOT_LABEL = { shadow: '阴影', light_source: '光源', reflection: '反射', exposure: '曝光', filter: '滤镜' }
const LEVEL_LABEL = { junior: '初级', middle: '中级', senior: '高级' }
const TARGET_LABEL = { all: '全部', worker: '兼职', admin: '管理', skill: '技能组' }
const NOTICE_TYPE_LABEL = { notice: '公告', flow: '流程', project: '项目动态', faq: 'FAQ' }

let toastTimer = null
function toast(msg, isError) {
  const el = $('#toast')
  el.textContent = msg
  el.classList.toggle('error', !!isError)
  el.classList.remove('hidden')
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => el.classList.add('hidden'), 2600)
}

async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) headers.Authorization = 'Bearer ' + token
  let res
  try {
    res = await fetch(API + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (e) {
    toast('网络异常', true)
    throw new Error('network')
  }
  let data
  try {
    data = await res.json()
  } catch (e) {
    data = { code: -1, message: '响应解析失败' }
  }
  if (res.status === 401) {
    logout()
    throw new Error(data.message || '未登录')
  }
  if (data.code !== 0) {
    toast(data.message || '操作失败', true)
    throw new Error(data.message)
  }
  return data.data
}

/* ---------------- 登录 / 退出 ---------------- */
function showApp(name) {
  $('#login-view').classList.add('hidden')
  $('#app-view').classList.remove('hidden')
  $('#admin-name').textContent = name || ''
  switchPage(currentPage || 'users')
}

function logout() {
  localStorage.removeItem(TOKEN_KEY)
  $('#app-view').classList.add('hidden')
  $('#login-view').classList.remove('hidden')
  $('#login-password').value = ''
}

function bindLogin() {
  $('#login-form').addEventListener('submit', async (e) => {
    e.preventDefault()
    const account = $('#login-account').value.trim()
    const password = $('#login-password').value
    if (!account || !password) return
    try {
      const data = await api('/auth/admin/login', { method: 'POST', body: { account, password } })
      localStorage.setItem(TOKEN_KEY, data.token)
      $('#login-error').classList.add('hidden')
      showApp((data.user && data.user.nickname) || (data.user && data.user.openid) || '管理员')
    } catch (err) {
      $('#login-error').textContent = err.message || '登录失败'
      $('#login-error').classList.remove('hidden')
    }
  })
  $('#logout-btn').addEventListener('click', logout)
}

function bindNav() {
  document.querySelectorAll('.sidebar nav a[data-page]').forEach((a) => {
    a.addEventListener('click', () => switchPage(a.dataset.page))
  })
}

function switchPage(page) {
  currentPage = page
  document.querySelectorAll('.sidebar nav a[data-page]').forEach((a) => {
    a.classList.toggle('active', a.dataset.page === page)
  })
  const renderers = { users: renderUsers, quality: renderQuality, certifications: renderCertifications, violations: renderViolations, notices: renderNotices, withdrawals: renderWithdrawals, ledger: renderLedger }
  ;(renderers[page] || renderUsers)()
}

/* ---------------- 用户 / 审批（T5-2） ---------------- */
async function renderUsers() {
  const status = $('#u-status') ? $('#u-status').value : ''
  const approval = $('#u-approval') ? $('#u-approval').value : ''
  const keyword = $('#u-keyword') ? $('#u-keyword').value.trim() : ''
  const q = new URLSearchParams()
  if (status) q.set('status', status)
  if (approval) q.set('approval_status', approval)
  if (keyword) q.set('keyword', keyword)
  const list = await api('/users?' + q.toString())
  const rows = list.map((u) => `
    <tr>
      <td>${u.id}</td>
      <td>${esc(u.real_name || '-')}</td>
      <td>${esc(u.phone || '-')}</td>
      <td>${u.role === 'admin' ? '管理员' : '兼职'}</td>
      <td><span class="tag ${u.approval_status}">${APPROVAL_LABEL[u.approval_status] || u.approval_status}</span></td>
      <td><span class="tag ${u.status}">${STATUS_LABEL[u.status] || u.status}</span></td>
      <td class="ops">
        ${u.approval_status === 'pending' ? `
          <button class="btn btn-sm btn-success" onclick="doApprove(${u.id})">通过</button>
          <button class="btn btn-sm btn-danger-ghost" onclick="doReject(${u.id})">驳回</button>` : ''}
        ${u.status === 'active'
          ? `<button class="btn btn-sm btn-danger-ghost" onclick="doBlock(${u.id})">封禁</button>`
          : `<button class="btn btn-sm btn-success" onclick="doUnblock(${u.id})">解封</button>`}
      </td>
    </tr>`).join('')
  $('#page-content').innerHTML = `
    <div class="page-title">用户 / 审批</div>
    <div class="panel">
      <div class="filters">
        <input id="u-keyword" placeholder="姓名 / 手机号 / 昵称" value="${esc(keyword)}" onkeydown="if(event.key==='Enter')renderUsers()">
        <select id="u-approval" onchange="renderUsers()">
          <option value="">审批状态:全部</option>
          <option value="pending" ${approval === 'pending' ? 'selected' : ''}>待审批</option>
          <option value="approved" ${approval === 'approved' ? 'selected' : ''}>已通过</option>
          <option value="rejected" ${approval === 'rejected' ? 'selected' : ''}>已驳回</option>
        </select>
        <select id="u-status" onchange="renderUsers()">
          <option value="">账号状态:全部</option>
          <option value="active" ${status === 'active' ? 'selected' : ''}>正常</option>
          <option value="blocked" ${status === 'blocked' ? 'selected' : ''}>已封禁</option>
        </select>
        <button class="btn" onclick="renderUsers()">查询</button>
      </div>
      <table>
        <thead><tr><th>ID</th><th>姓名</th><th>手机号</th><th>角色</th><th>审批</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="empty">暂无用户</td></tr>'}</tbody>
      </table>
    </div>`
}

async function doApprove(id) { await api(`/users/${id}/approve`, { method: 'POST' }); toast('已通过'); renderUsers() }
async function doReject(id) { await api(`/users/${id}/reject`, { method: 'POST' }); toast('已驳回'); renderUsers() }
async function doBlock(id) { await api(`/users/${id}/block`, { method: 'POST' }); toast('已封禁'); renderUsers() }
async function doUnblock(id) { await api(`/users/${id}/unblock`, { method: 'POST' }); toast('已解封'); renderUsers() }

/* ---------------- 核验管理（T5-3） ---------------- */
async function renderQuality() {
  const list = await api('/quality-checks/pending-assignments')
  const rows = list.map((a) => `
    <tr>
      <td>${a.assignment_id}</td>
      <td>${esc(a.user_name || '-')}</td>
      <td>${esc(a.task_name || a.task_id)}</td>
      <td>${a.submit_time ? new Date(a.submit_time).toLocaleString() : '-'}</td>
      <td class="ops">
        <button class="btn btn-sm btn-success" onclick="doQcPass(${a.assignment_id})">回写通过</button>
        <button class="btn btn-sm btn-danger-ghost" onclick="doQcReject(${a.assignment_id})">回写未过</button>
      </td>
    </tr>`).join('')
  $('#page-content').innerHTML = `
    <div class="page-title">核验管理 <span style="font-size:13px;color:var(--muted)">（外部系统核验后，在此回写结果）</span></div>
    <div class="panel">
      <table>
        <thead><tr><th>作业ID</th><th>作业人</th><th>任务</th><th>提交时间</th><th>操作</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="5" class="empty">暂无待核验作业</td></tr>'}</tbody>
      </table>
    </div>`
}

async function doQcPass(id) {
  const externalRefNo = (prompt('外部核验单号（通过必填）') || '').trim()
  if (!externalRefNo) { toast('通过必须填写核验单号', true); return }
  const remark = (prompt('备注（可空）') || '').trim()
  await api('/quality-checks/writeback', { method: 'POST', body: { assignment_id: id, result: 'pass', external_ref_no: externalRefNo, remark } })
  toast('已回写通过'); renderQuality()
}
async function doQcReject(id) {
  const remark = (prompt('备注（可空）') || '').trim()
  await api('/quality-checks/writeback', { method: 'POST', body: { assignment_id: id, result: 'reject', remark } })
  toast('已回写未过'); renderQuality()
}

/* ---------------- 能力认证（T5-4） ---------------- */
async function renderCertifications() {
  const list = await api('/certifications/list')
  const rows = list.map((c) => `
    <tr>
      <td>${c.id}</td>
      <td>${esc(c.user_name || '-')}</td>
      <td>${esc(c.task_name || c.task_id)}</td>
      <td>${ANNOT_LABEL[c.annot_type] || c.annot_type || '-'}</td>
      <td>${c.exam_passed ? '通过' : '未过'}</td>
      <td>${LEVEL_LABEL[c.level] || '-'}</td>
      <td>${c.pass_rate != null ? c.pass_rate : '-'}</td>
      <td>${c.review_time ? new Date(c.review_time).toLocaleString() : '<span style="color:#b06000">待评级</span>'}</td>
      <td class="ops"><button class="btn btn-sm" onclick="openRate(${c.id},${JSON.stringify(esc(c.user_name || ''))})">评级</button></td>
    </tr>`).join('')
  $('#page-content').innerHTML = `
    <div class="page-title">能力认证管理</div>
    <div class="panel">
      <table>
        <thead><tr><th>ID</th><th>姓名</th><th>任务</th><th>标注类型</th><th>考试</th><th>等级</th><th>通过率</th><th>复核时间</th><th>操作</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="9" class="empty">暂无认证记录</td></tr>'}</tbody>
      </table>
    </div>`
}

function openRate(id, userName) {
  const body = prompt(`为 ${userName}（认证#${id}）评级\n请输入: 等级|是否通过|通过率\n例: senior|是|85  或  junior|否|0`, 'middle|是|80')
  if (!body) return
  const [level, passed, rate] = body.split('|').map((s) => (s || '').trim())
  doRate(id, { level, exam_passed: passed === '是', pass_rate: rate ? Number(rate) : undefined })
}
async function doRate(id, payload) {
  await api(`/certifications/${id}/rate`, { method: 'POST', body: payload })
  toast('已保存评级'); renderCertifications()
}

/* ---------------- 违规管理（T5-6） ---------------- */
async function renderViolations() {
  const openid = $('#v-openid') ? $('#v-openid').value.trim() : ''
  const q = openid ? '?openid=' + encodeURIComponent(openid) : ''
  const list = await api('/violations' + q)
  const rows = list.map((v) => `
    <tr>
      <td>${v.id}</td>
      <td>${esc(v.user_name || '-')}</td>
      <td>${esc(v.openid)}</td>
      <td>${TYPE_LABEL[v.type] || v.type}</td>
      <td><span class="tag ${v.punish_level === 'block' ? 'rejected' : ''}">${PUNISH_LABEL[v.punish_level] || v.punish_level}</span></td>
      <td>${esc(v.reason || '-')}</td>
      <td>${v.create_time ? new Date(v.create_time).toLocaleString() : '-'}</td>
    </tr>`).join('')
  $('#page-content').innerHTML = `
    <div class="page-title">违规 / 黑名单管理</div>
    <div class="panel">
      <h3>新增违规</h3>
      <div class="form-grid">
        <label>用户 openid<input id="v-new-openid" placeholder="用户 openid"></label>
        <label>违规类型<select id="v-new-type">
          ${Object.entries(TYPE_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}
        </select></label>
        <label>处罚<select id="v-new-punish">
          ${Object.entries(PUNISH_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}
        </select></label>
        <label>原因<textarea id="v-new-reason" placeholder="违规原因"></textarea></label>
        <label>&nbsp;<button class="btn" onclick="doNewViolation()">记录违规</button></label>
      </div>
    </div>
    <div class="panel">
      <div class="filters">
        <input id="v-openid" placeholder="按 openid 筛选" value="${esc(openid)}" onkeydown="if(event.key==='Enter')renderViolations()">
        <button class="btn" onclick="renderViolations()">查询</button>
      </div>
      <table>
        <thead><tr><th>ID</th><th>姓名</th><th>openid</th><th>类型</th><th>处罚</th><th>原因</th><th>时间</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="empty">暂无违规记录</td></tr>'}</tbody>
      </table>
    </div>`
}

async function doNewViolation() {
  const openid = $('#v-new-openid').value.trim()
  if (!openid) { toast('请填写用户 openid', true); return }
  await api('/violations', {
    method: 'POST',
    body: { openid, type: $('#v-new-type').value, punish_level: $('#v-new-punish').value, reason: $('#v-new-reason').value.trim() },
  })
  toast('已记录违规'); renderViolations()
}

/* ---------------- 公告管理（T5-7） ---------------- */
async function renderNotices() {
  const list = await api('/notices')
  const rows = list.map((n) => `
    <tr>
      <td>${n.id}</td>
      <td>${esc(n.title)}</td>
      <td>${esc((n.content || '').slice(0, 40))}${(n.content || '').length > 40 ? '…' : ''}</td>
      <td>${TARGET_LABEL[n.target] || n.target}</td>
      <td>${NOTICE_TYPE_LABEL[n.type] || n.type}</td>
      <td>${n.create_time ? new Date(n.create_time).toLocaleString() : '-'}</td>
    </tr>`).join('')
  $('#page-content').innerHTML = `
    <div class="page-title">公告 / 流程 / 动态 / FAQ 管理</div>
    <div class="panel">
      <h3>发布</h3>
      <div class="form-grid">
        <label>标题<input id="n-title"></label>
        <label>内容<textarea id="n-content"></textarea></label>
        <label>定向<select id="n-target">${Object.entries(TARGET_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
        <label>类型<select id="n-type">${Object.entries(NOTICE_TYPE_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
        <label>&nbsp;<button class="btn" onclick="doNewNotice()">发布</button></label>
      </div>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>ID</th><th>标题</th><th>内容</th><th>定向</th><th>类型</th><th>时间</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="6" class="empty">暂无公告</td></tr>'}</tbody>
      </table>
    </div>`
}

async function doNewNotice() {
  const title = $('#n-title').value.trim()
  const content = $('#n-content').value.trim()
  if (!title || !content) { toast('标题与内容必填', true); return }
  await api('/notices', { method: 'POST', body: { title, content, target: $('#n-target').value, type: $('#n-type').value } })
  toast('已发布'); renderNotices()
}

/* ---------------- 提现确认（T4-3 半自动回写） ---------------- */
const WD_STATUS_LABEL = { pending: '提现中', paid: '已到账', rejected: '已拒绝' }

async function renderWithdrawals() {
  const status = $('#wd-status') ? $('#wd-status').value : 'pending'
  const q = status ? '?status=' + status : ''
  const list = await api('/wallet/withdrawals/admin' + q)
  const rows = list.map((w) => `
    <tr>
      <td>${w.id}</td>
      <td>${esc(w.user_name || '-')}</td>
      <td>${esc(w.openid)}</td>
      <td>${w.amount}</td>
      <td>${w.bank_account ? `${esc(w.bank_account.bankName || '')} ···${esc(w.bank_account.cardNo ? w.bank_account.cardNo.slice(-4) : '')}（${esc(w.bank_account.cardHolder || '')}）` : '-'}</td>
      <td><span class="tag ${w.status}">${WD_STATUS_LABEL[w.status] || w.status}</span></td>
      <td>${w.apply_time ? new Date(w.apply_time).toLocaleString() : '-'}</td>
      <td>${w.paid_time ? new Date(w.paid_time).toLocaleString() : '-'}</td>
      <td class="ops">${w.status === 'pending'
        ? `<button class="btn btn-sm btn-success" onclick="doConfirmPaid(${w.id})">确认到账</button>`
        : `${w.pay_ref_no ? ('单号:' + esc(w.pay_ref_no) + ' ') : ''}${w.paid_source ? (w.paid_source === 'manual' ? '手动' : '自动') : ''}`}
      </td>
    </tr>`).join('')
  $('#page-content').innerHTML = `
    <div class="page-title">提现确认 <span style="font-size:13px;color:var(--muted)">（免审核，财务确认到账置 paid，D4-2 半自动兜底）</span></div>
    <div class="panel">
      <div class="filters">
        <select id="wd-status" onchange="renderWithdrawals()">
          <option value="pending" ${status === 'pending' ? 'selected' : ''}>待到账</option>
          <option value="paid" ${status === 'paid' ? 'selected' : ''}>已到账</option>
          <option value="rejected" ${status === 'rejected' ? 'selected' : ''}>已拒绝</option>
        </select>
      </div>
      <table>
        <thead><tr><th>ID</th><th>姓名</th><th>openid</th><th>金额</th><th>收款账户</th><th>状态</th><th>申请时间</th><th>到账时间</th><th>操作</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="9" class="empty">暂无提现记录</td></tr>'}</tbody>
      </table>
    </div>`
}

async function doConfirmPaid(id) {
  const payRefNo = (prompt('到账单号（可空，用于对账）') || '').trim()
  await api(`/wallet/withdrawals/${id}/confirm`, { method: 'POST', body: { pay_ref_no: payRefNo, paid_source: 'manual' } })
  toast('已确认到账'); renderWithdrawals()
}

/* ---------------- 台账 / 对账导出（T5-5，对接 T4-5） ---------------- */
async function renderLedger() {
  const start = $('#ledger-start') ? $('#ledger-start').value : ''
  const end = $('#ledger-end') ? $('#ledger-end').value : ''
  const today = new Date().toISOString().slice(0, 10)
  const s = start || today
  const e = end || today
  const q = new URLSearchParams({ start_date: s, end_date: e })
  const data = await api('/wallet/ledger?' + q.toString())
  const days = data.days || []
  const rows = days.map((d) => `
    <tr>
      <td>${d.date}</td>
      <td>${d.commission_count}</td>
      <td>${d.commission_amount}</td>
      <td>${d.withdrawal_count}</td>
      <td>${d.withdrawal_amount}</td>
      <td>${d.net_amount}</td>
    </tr>`).join('')
  const sm = data.summary || {}
  $('#page-content').innerHTML = `
    <div class="page-title">台账 / 对账导出 <span style="font-size:13px;color:var(--muted)">（按日聚合佣金 + 提现，含汇总行）</span></div>
    <div class="panel">
      <div class="filters">
        <input id="ledger-start" type="date" value="${s}">
        <span>至</span>
        <input id="ledger-end" type="date" value="${e}">
        <button class="btn" onclick="renderLedger()">查询</button>
        <button class="btn btn-ghost" onclick="downloadLedger('csv')">导出 CSV</button>
        <button class="btn btn-success" onclick="downloadLedger('excel')">导出 Excel</button>
      </div>
      <table>
        <thead><tr><th>日期</th><th>佣金笔数</th><th>佣金金额</th><th>提现笔数</th><th>提现金额</th><th>净结余</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="6" class="empty">暂无数据</td></tr>'}
          <tr style="font-weight:600;background:#f0f4ff">
            <td>汇总</td><td>${sm.commission_count || 0}</td><td>${sm.commission_amount || '0'}</td>
            <td>${sm.withdrawal_count || 0}</td><td>${sm.withdrawal_amount || '0'}</td><td>${sm.net_amount || '0'}</td>
          </tr>
        </tbody>
      </table>
    </div>`
}

function downloadLedger(fmt) {
  const s = $('#ledger-start').value
  const e = $('#ledger-end').value
  window.open(`/api/wallet/ledger?start_date=${s}&end_date=${e}&format=${fmt}`, '_blank')
}

/* ---------------- 初始化 ---------------- */
document.addEventListener('DOMContentLoaded', () => {
  bindLogin()
  bindNav()
  if (localStorage.getItem(TOKEN_KEY)) {
    showApp('管理员')
  }
})