/**
 * TraceBack API - 回溯分析接口
 */
import api from './index'

// 获取所有Agent信息
export const getAgents = () => api.get('/analysis/agents')

// 创建分析
export const createAnalysis = (data) => api.post('/analysis/create', data)

// 启动分析
export const startAnalysis = (analysisId) => api.post('/analysis/start', { analysis_id: analysisId })

// 停止分析
export const stopAnalysis = (analysisId) => api.post('/analysis/stop', { analysis_id: analysisId })

// 获取分析状态
export const getAnalysisStatus = (analysisId) => api.get(`/analysis/status/${analysisId}`)

// 列出分析任务
export const listAnalyses = (projectId, limit = 50) => {
  const params = { limit }
  if (projectId) params.project_id = projectId
  return api.get('/analysis/list', { params })
}

// 获取因果网络图数据
export const getCausalGraph = (analysisId) => api.get(`/analysis/causal-graph/${analysisId}`)

// 获取时间线数据
export const getTimeline = (analysisId) => api.get(`/analysis/timeline/${analysisId}`)

// 获取质证辩论消息（支持增量）
export const getDebateMessages = (analysisId, sinceIndex = 0) =>
  api.get(`/analysis/debate/${analysisId}`, { params: { since: sinceIndex } })

// 获取证据链数据
export const getEvidenceChain = (analysisId) => api.get(`/analysis/evidence/${analysisId}`)
