import service, { requestWithRetry } from './index'

/**
 * 生成本体（上传文档和模拟需求）
 * @param {Object} data - 包含files, simulation_requirement, project_name等
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return requestWithRetry(() => 
    service({
      url: '/graph/ontology/generate',
      method: 'post',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  )
}

/**
 * 构建图谱
 * @param {Object} data - 包含project_id, graph_name等
 * @returns {Promise}
 */
export function buildGraph(data) {
  return requestWithRetry(() =>
    service({
      url: '/graph/build',
      method: 'post',
      data
    })
  )
}

/**
 * 查询任务状态（轮询用，404 不抛异常）
 * @param {String} taskId - 任务ID
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/graph/task/${taskId}`,
    method: 'get'
  }).catch(err => {
    // 404 = 任务不存在（后端重启等），返回 success:false 而非抛异常
    if (err.response && err.response.status === 404) {
      return { success: false, error: 'Task not found', status: 404 }
    }
    throw err
  })
}

/**
 * 获取项目信息（轮询用，404 不抛异常）
 * @param {String} projectId - 项目ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/graph/project/${projectId}`,
    method: 'get'
  }).catch(err => {
    if (err.response && err.response.status === 404) {
      return { success: false, error: 'Project not found', status: 404 }
    }
    throw err
  })
}

/**
 * 获取图谱数据
 * @param {String} graphId - 图谱ID
 * @returns {Promise}
 */
export function getGraphData(graphId) {
  return service({
    url: `/graph/data/${graphId}`,
    method: 'get'
  })
}
