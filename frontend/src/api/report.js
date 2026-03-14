import service, { requestWithRetry } from './index'

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return requestWithRetry(() => service.post('/report/generate', data), 3, 1000)
}

/**
 * 获取报告生成状态
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/report/${reportId}`)
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return requestWithRetry(() => service.post('/report/chat', data), 3, 1000)
}

/**
 * 下载报告 docx 文档
 * @param {string} reportId
 */
export const downloadReport = async (reportId) => {
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
  const url = `${baseURL}/report/${reportId}/download`
  
  try {
    const response = await fetch(url)
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || '下载失败')
    }
    
    const blob = await response.blob()
    const contentDisposition = response.headers.get('Content-Disposition') || ''
    let filename = `report_${reportId}.docx`
    
    // 尝试从 Content-Disposition 提取文件名
    const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/) 
        || contentDisposition.match(/filename="?([^"]+)"?/)
    if (filenameMatch) {
      filename = decodeURIComponent(filenameMatch[1])
    }
    if (filenameMatch) {
      filename = decodeURIComponent(filenameMatch[1])
    }
    
    // 触发浏览器下载
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
    
    return { success: true }
  } catch (err) {
    return { success: false, error: err.message }
  }
}
