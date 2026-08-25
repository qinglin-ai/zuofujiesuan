const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

Page({
  data: {
    logged: false,
    user: null,
    ping: null,
    dbOk: null
  },

  onShow() {
    const token = tokenManager.getToken()
    this.setData({ logged: !!token })
  },

  async onHealth() {
    try {
      const data = await request.get('/api/health/ping', {}, { needAuth: false })
      this.setData({ ping: data })
      this.setData({ dbOk: await this._checkDb() })
    } catch (e) {
      this.setData({ ping: e })
    }
  },

  async _checkDb() {
    try {
      await request.get('/api/health/db', {}, { needAuth: false })
      return true
    } catch (e) {
      return false
    }
  },

  onLogout() {
    tokenManager.clearToken()
    this.setData({ logged: false })
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  }
})