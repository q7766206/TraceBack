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
  try {
    // 使用 axios 获取文件，设置 responseType 为 blob
    const response = await service({
      url: `/report/${reportId}/download`,
      method: 'get',
      responseType: 'blob',  // 重要：告诉 axios 返回 blob 类型
      timeout: 60000  // 下载超时时间 60 秒
    })
    
    // 从响应头获取文件名
    const contentDisposition = response.headers['content-disposition'] || ''
    let filename = `report_${reportId}.docx`
    
    // 尝试从 Content-Disposition 提取文件名
    const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/) 
        || contentDisposition.match(/filename="?([^"]+)"?/)
    if (filenameMatch && filenameMatch[1]) {
      filename = decodeURIComponent(filenameMatch[1])
    }
    
    // 创建 blob URL 并触发下载
    const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    
    return { success: true }
  } catch (err) {
    console.error('下载报告失败:', err)
    return { success: false, error: err.message || '下载失败' }
  }
}
