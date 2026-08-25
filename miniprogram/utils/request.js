const tokenManager = require('./token')

/**
 * 统一请求封装：自动携带 Authorization: Bearer <token>，解析 REST 响应。
 * 后端约定响应体 { code, message, data }；code===0 视为成功。
 */
function request({ url, method = 'GET', data = {}, needAuth = true }) {
  const baseUrl = getApp().globalData.backendBaseUrl
  const header = { 'Content-Type': 'application/json' }
  if (needAuth) {
    const token = tokenManager.getToken()
    if (token) header.Authorization = `Bearer ${token}`
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: baseUrl + url,
      method,
      data,
      header,
      success(res) {
        const body = res.data || {}
        if (res.statusCode === 401) {
          tokenManager.clearToken()
          reject({ code: 401, message: '未登录' })
          return
        }
        if (body.code === 0) {
          resolve(body.data)
        } else {
          reject(body)
        }
      },
      fail(err) {
        reject({ code: -1, message: '网络异常', detail: err })
      }
    })
  })
}

module.exports = {
  get: (url, data, opts) => request({ url, data, ...opts }),
  post: (url, data, opts) => request({ url, method: 'POST', data, ...opts })
}