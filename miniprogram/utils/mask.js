/**
 * 隐私脱敏口径（展示用，统一在此定义，避免各页面不一致导致信息泄露）：
 * - 手机号：保留前 3 位与后 4 位，如 187****4688（非 11 位原样返回）
 * - 真实姓名：保留首末字，如 刘彦余→刘*余、张三→张*（单字不遮蔽）
 */
function maskPhone(phone) {
  if (!phone) return ''
  return phone.length === 11 ? phone.slice(0, 3) + '****' + phone.slice(7) : phone
}

function maskName(name) {
  const s = (name || '').trim()
  if (s.length < 2) return s
  if (s.length === 2) return s.slice(0, 1) + '*'
  return s.slice(0, 1) + '*'.repeat(s.length - 2) + s.slice(-1)
}

module.exports = { maskPhone, maskName }