const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

const WD_STATUS = { pending: '提现中', paid: '已到账', rejected: '已拒绝' }

Page({
  data: {
    loading: true,
    error: '',
    info: { available_balance: '0', total_income: '0', total_withdrawn: '0', has_bank: false, bank_info: null, bank_tail: '' },
    bank: { bankName: '', cardNo: '', cardHolder: '' },
    withdrawAmount: '',
    canWithdraw: false,
    activeTab: 'commission',
    commissions: [],
    withdrawals: [],
  },

  onShow() {
    if (!tokenManager.getToken()) {
      wx.navigateTo({ url: '/pages/login/login' })
      return
    }
    this._load()
  },

  onPullDownRefresh() {
    this._load().then(() => wx.stopPullDownRefresh())
  },

  async _load() {
    this.setData({ loading: true, error: '' })
    try {
      const info = await request.get('/api/wallet/me')
      const commissions = await request.get('/api/wallet/commissions')
      const wds = await request.get('/api/wallet/withdrawals')
      const bank = info.bank_info || { bankName: '', cardNo: '', cardHolder: '' }
      const bank_tail = info.bank_info && info.bank_info.cardNo
        ? `${info.bank_info.bankName || ''} ···${String(info.bank_info.cardNo).slice(-4)}（${info.bank_info.cardHolder || ''}）`
        : ''
      const withdrawals = wds.map((w) => ({ ...w, status_text: WD_STATUS[w.status] || w.status }))
      this.setData({
        info: { ...info, bank_tail },
        commissions,
        withdrawals,
        bank: { bankName: bank.bankName || '', cardNo: bank.cardNo || '', cardHolder: bank.cardHolder || '' },
        canWithdraw: info.has_bank && Number(info.available_balance) > 0,
        loading: false,
      })
    } catch (e) {
      this.setData({ loading: false, error: (e && e.message) || '加载失败' })
    }
  },

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.key })
  },

  onBankInput(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ ['bank.' + key]: e.detail.value })
  },

  async onBindBank() {
    const { bankName, cardNo, cardHolder } = this.data.bank
    if (!bankName || !cardNo || !cardHolder) {
      wx.showToast({ title: '请填写完整开户行/卡号/持卡人', icon: 'none' })
      return
    }
    try {
      await request.post('/api/wallet/bank', this.data.bank)
      wx.showToast({ title: '绑定成功', icon: 'success' })
      this._load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '绑定失败', icon: 'none' })
    }
  },

  onAmountInput(e) {
    this.setData({ withdrawAmount: e.detail.value })
  },

  async onWithdraw() {
    const amount = Number(this.data.withdrawAmount)
    if (!amount || amount <= 0) {
      wx.showToast({ title: '请输入有效金额', icon: 'none' })
      return
    }
    if (amount > Number(this.data.info.available_balance)) {
      wx.showToast({ title: '余额不足', icon: 'none' })
      return
    }
    const res = await wx.showModal({ title: '确认提现', content: `申请提现 ￥${amount}？`, confirmColor: '#1989fa' })
    if (!res.confirm) return
    try {
      await request.post('/api/wallet/withdrawals', { amount: this.data.withdrawAmount })
      wx.showToast({ title: '申请成功', icon: 'success' })
      this.setData({ withdrawAmount: '' })
      this._load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '提现失败', icon: 'none' })
    }
  },
})