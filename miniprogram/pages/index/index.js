const request = require('../../utils/request')
const tokenManager = require('../../utils/token')

// 开发环境判定：仅开发版展示连通性诊断，试用/正式版不展示
function isDevBuild() {
  try {
    const info = wx.getAccountInfoSync()
    return info && info.miniProgram && info.miniProgram.envVersion === 'develop'
  } catch (e) {
    return true
  }
}

Page({
  data: {
    logged: false,
    user: null,
    ping: null,
    dbOk: null,
    devMode: false
  },

  onLoad() {
    this.setData({ devMode: isDevBuild() })
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

  goCertify() {
    wx.navigateTo({ url: '/pages/certify/certify' })
  },

  goLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  }
})