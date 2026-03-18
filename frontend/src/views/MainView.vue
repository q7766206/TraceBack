<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">TRACEBACK</div>
      </div>
      
      <div class="header-center">
        <div class="view-switcher">
          <button 
            v-for="mode in ['graph', 'split', 'workbench']" 
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ { graph: '图谱', split: '双栏', workbench: '工作台' }[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">Step {{ currentStep }}/4</span>
          <span class="step-name">{{ stepNames[currentStep - 1] }}</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
        <div class="step-divider"></div>
        <div class="action-buttons">
          <button class="action-btn pause-btn" @click="handlePause">
            {{ isPaused ? '恢复' : '暂停' }}
          </button>
          <button class="action-btn home-btn" @click="handleReturnHome">
            返回首页
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel 
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          :isSimulating="isSimulating"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step Components -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <!-- Step 1: 图谱构建 -->
        <Step1GraphBuild 
          v-if="currentStep === 1"
          :currentPhase="currentPhase"
          :projectData="projectData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @next-step="handleNextStep"
          @pause="handlePause"
          @return-home="handleReturnHome"
        />
        <!-- Step 2: 环境搭建 -->
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
          @pause="handlePause"
          @return-home="handleReturnHome"
        />
        <!-- Step 3: 开始模拟 -->
        <Step3Simulation
          v-else-if="currentStep === 3"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
          @pause="handlePause"
          @return-home="handleReturnHome"
          @update-simulating-status="handleSimulatingStatusUpdate"
        />
        <!-- Step 4: 报告生成 -->
        <Step4Report
          v-else-if="currentStep === 4"
          :reportId="projectData?.report_id"
          :simulationId="projectData?.simulation_id"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
          @pause="handlePause"
          @return-home="handleReturnHome"
        />

      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step1GraphBuild from '../components/Step1GraphBuild.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import Step3Simulation from '../components/Step3Simulation.vue'
import Step4Report from '../components/Step4Report.vue'
import { generateOntology, getProject, buildGraph, getTaskStatus, getGraphData } from '../api/graph'
import { getPendingUpload, clearPendingUpload } from '../store/pendingUpload'

const route = useRoute()
const router = useRouter()

// Layout State
const viewMode = ref('split') // graph | split | workbench

// Step State
const currentStep = ref(1) // 1: 图谱构建, 2: 环境搭建, 3: 开始模拟, 4: 报告生成
const stepNames = ['图谱构建', '环境搭建', '开始模拟', '报告生成']

// Data State
const currentProjectId = ref(route.params.projectId)
const loading = ref(false)
const graphLoading = ref(false)
const error = ref('')
const projectData = ref(null)
const graphData = ref(null)
const currentPhase = ref(-1) // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyProgress = ref(null)
const buildProgress = ref(null)
const systemLogs = ref([])
const isPaused = ref(false)
const isSimulating = ref(false)

// Polling timers
let pollTimer = null
let graphPollTimer = null

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- Status Computed ---
const statusClass = computed(() => {
  if (error.value) return 'error'
  if (currentPhase.value >= 2) return 'completed'
  return 'processing'
})

const statusText = computed(() => {
  if (error.value) return 'Error'
  if (currentPhase.value >= 2) return 'Ready'
  if (currentPhase.value === 1) return 'Building Graph'
  if (currentPhase.value === 0) return 'Generating Ontology'
  return 'Initializing'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  // Keep last 100 logs
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleNextStep = (params = {}) => {
  if (currentStep.value < 4) {
    currentStep.value++
    addLog(`进入 Step ${currentStep.value}: ${stepNames[currentStep.value - 1]}`)
    
    // 如果是从 Step 2 进入 Step 3，记录模拟轮数配置
    if (currentStep.value === 3 && params.maxRounds) {
      addLog(`自定义模拟轮数: ${params.maxRounds} 轮`)
    }
  }
}

const handleGoBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    addLog(`返回 Step ${currentStep.value}: ${stepNames[currentStep.value - 1]}`)
  }
}

const handlePause = () => {
  if (isPaused.value) {
    // 恢复操作
    isPaused.value = false
    addLog('操作已恢复')
    
    // 根据当前状态恢复轮询
    if (projectData.value) {
      if (projectData.value.status === 'graph_building' && projectData.value.graph_build_task_id) {
        startPollingTask(projectData.value.graph_build_task_id)
      } else if (projectData.value.status === 'created' && projectData.value.ontology_task_id) {
        startPollingOntologyTask(projectData.value.ontology_task_id)
      }
      // 始终恢复图谱轮询
      startGraphPolling()
    }
  } else {
    // 暂停操作
    isPaused.value = true
    stopPolling()
    stopGraphPolling()
    stopOntologyPolling()
    addLog('操作已暂停')
  }
}

const handleReturnHome = () => {
  stopPolling()
  stopGraphPolling()
  stopOntologyPolling()
  router.push('/')
  addLog('返回首页')
}

const handleSimulatingStatusUpdate = (status) => {
  isSimulating.value = status
  addLog(status ? '模拟开始' : '模拟结束')
}

// --- Data Logic ---

const initProject = async () => {
  addLog('Project view initialized.')
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadProject()
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()
  if (!pending.isPending || pending.files.length === 0) {
    error.value = 'No pending files found.'
    addLog('Error: No pending files found for new project.')
    return
  }
  
  try {
    loading.value = true
    currentPhase.value = 0
    ontologyProgress.value = { message: 'Uploading and analyzing docs...' }
    addLog('Starting ontology generation: Uploading files...')
    
    const formData = new FormData()
    pending.files.forEach(f => formData.append('files', f))
    formData.append('simulation_requirement', pending.simulationRequirement)
    
    const res = await generateOntology(formData)
    if (res.success) {
      clearPendingUpload()
      currentProjectId.value = res.data.project_id
      projectData.value = res.data
      
      router.replace({ name: 'Process', params: { projectId: res.data.project_id } })
      
      // 异步模式：后端立即返回 task_id，前端轮询本体生成状态
      if (res.data.task_id) {
        currentPhase.value = 0
        ontologyProgress.value = { message: '正在生成本体定义...' }
        addLog(`Ontology generation task started: ${res.data.task_id}`)
        startPollingOntologyTask(res.data.task_id)
      } else if (res.data.ontology) {
        // 兼容旧同步模式
        ontologyProgress.value = null
        addLog(`Ontology generated successfully for project ${res.data.project_id}`)
        await startBuildGraph()
      }
    } else {
      error.value = res.error || 'Ontology generation failed'
      addLog(`Error generating ontology: ${error.value}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in handleNewProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const loadProject = async () => {
  try {
    loading.value = true
    addLog(`Loading project ${currentProjectId.value}...`)
    const res = await getProject(currentProjectId.value)
    if (res.success) {
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      addLog(`Project loaded. Status: ${res.data.status}`)
      
      if (res.data.status === 'created' && res.data.ontology_task_id) {
        // 本体还在生成中，轮询任务状态
        currentPhase.value = 0
        ontologyProgress.value = { message: '正在生成本体定义...' }
        startPollingOntologyTask(res.data.ontology_task_id)
      } else if (res.data.status === 'ontology_generated' && !res.data.graph_id) {
        await startBuildGraph()
      } else if (res.data.status === 'graph_building' && res.data.graph_build_task_id) {
        currentPhase.value = 1
        startPollingTask(res.data.graph_build_task_id)
        startGraphPolling()
      } else if (res.data.status === 'graph_completed' && res.data.graph_id) {
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
        startGraphPolling()
      }
    } else {
      error.value = res.error
      addLog(`Error loading project: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in loadProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const updatePhaseByStatus = (status) => {
  switch (status) {
    case 'created':
    case 'ontology_generated': currentPhase.value = 0; break;
    case 'graph_building': currentPhase.value = 1; break;
    case 'graph_completed': currentPhase.value = 2; break;
    case 'failed': error.value = 'Project failed'; break;
  }
}

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    buildProgress.value = { progress: 0, message: 'Starting build...' }
    addLog('Initiating graph build...')
    
    const res = await buildGraph({ project_id: currentProjectId.value })
    if (res.success) {
      addLog(`Graph build task started. Task ID: ${res.data.task_id}`)
      startGraphPolling()
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(`Error starting build: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in startBuildGraph: ${err.message}`)
  }
}

const startGraphPolling = () => {
  addLog('Started polling for graph data...')
  fetchGraphData()
  graphPollTimer = setInterval(fetchGraphData, 10000)
}

const fetchGraphData = async () => {
  try {
    // Refresh project info to check for graph_id
    const projRes = await getProject(currentProjectId.value)
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id)
      if (gRes.success) {
        graphData.value = gRes.data
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0
        addLog(`Graph data refreshed. Nodes: ${nodeCount}, Edges: ${edgeCount}`)
      }
    }
  } catch (err) {
    console.warn('Graph fetch error:', err)
  }
}

// --- Ontology Task Polling ---
let ontologyPollTimer = null

const startPollingOntologyTask = (taskId) => {
  pollOntologyTaskStatus(taskId)
  ontologyPollTimer = setInterval(() => pollOntologyTaskStatus(taskId), 2000)
}

const stopOntologyPolling = () => {
  if (ontologyPollTimer) {
    clearInterval(ontologyPollTimer)
    ontologyPollTimer = null
  }
}

let _ontologyPollFailCount = 0

const pollOntologyTaskStatus = async (taskId) => {
  try {
    const res = await getTaskStatus(taskId)
    if (res.success) {
      _ontologyPollFailCount = 0
      const task = res.data
      
      if (task.message && task.message !== ontologyProgress.value?.message) {
        addLog(task.message)
      }
      ontologyProgress.value = { progress: task.progress || 0, message: task.message || '正在生成本体定义...' }
      
      if (task.status === 'completed') {
        stopOntologyPolling()
        ontologyProgress.value = null
        addLog('Ontology generation completed.')
        
        // 重新加载项目数据（此时本体已生成）
        const projRes = await getProject(currentProjectId.value)
        if (projRes.success) {
          projectData.value = projRes.data
        }
        
        // 自动进入图谱构建
        await startBuildGraph()
      } else if (task.status === 'failed') {
        stopOntologyPolling()
        ontologyProgress.value = null
        error.value = task.error || '本体生成失败'
        addLog(`Ontology generation failed: ${task.error}`)
      }
    } else {
      _ontologyPollFailCount++
      if (_ontologyPollFailCount >= 3) {
        stopOntologyPolling()
        error.value = '本体生成任务已失效，请返回首页重新提交'
        addLog(`Ontology task ${taskId} lost. Stopped polling.`)
      }
    }
  } catch (e) {
    _ontologyPollFailCount++
    console.error('Ontology poll error:', e)
    if (_ontologyPollFailCount >= 3) {
      stopOntologyPolling()
      error.value = '与后端连接中断，请检查服务状态'
      addLog('Ontology polling stopped after consecutive errors.')
    }
  }
}

const startPollingTask = (taskId) => {
  pollTaskStatus(taskId)
  pollTimer = setInterval(() => pollTaskStatus(taskId), 2000)
}

let _pollFailCount = 0

const pollTaskStatus = async (taskId) => {
  try {
    const res = await getTaskStatus(taskId)
    if (res.success) {
      _pollFailCount = 0  // 重置失败计数
      const task = res.data
      
      // Log progress message if it changed
      if (task.message && task.message !== buildProgress.value?.message) {
        addLog(task.message)
      }
      
      buildProgress.value = { progress: task.progress || 0, message: task.message }
      
      // 检查是否有增量图谱数据，用于实时渲染
      if (task.progress_detail && task.progress_detail.incremental_graph) {
        const incrementalGraph = task.progress_detail.incremental_graph
        if (incrementalGraph.nodes && incrementalGraph.edges) {
          // 使用增量数据更新图谱，实现实时渲染
          graphData.value = {
            ...(graphData.value || {}),
            nodes: incrementalGraph.nodes,
            edges: incrementalGraph.edges,
            node_count: incrementalGraph.node_count,
            edge_count: incrementalGraph.edge_count
          }
          addLog(`实时图谱更新: ${incrementalGraph.node_count} 节点, ${incrementalGraph.edge_count} 边`)
        }
      }
      
      if (task.status === 'completed') {
        addLog('Graph build task completed.')
        stopPolling()
        currentPhase.value = 2
        
        // Final load
        const projRes = await getProject(currentProjectId.value)
        if (projRes.success && projRes.data.graph_id) {
            projectData.value = projRes.data
            await loadGraph(projRes.data.graph_id)
        }
      } else if (task.status === 'failed') {
        stopPolling()
        error.value = task.error
        addLog(`Graph build task failed: ${task.error}`)
      }
    } else {
      // 接口返回了但 success=false（如 404 任务不存在）
      _pollFailCount++
      if (_pollFailCount >= 3) {
        stopPolling()
        stopGraphPolling()
        error.value = '任务已失效（后端可能已重启），请返回首页重新提交分析'
        addLog(`Task ${taskId} not found after ${_pollFailCount} retries. Stopped polling.`)
      }
    }
  } catch (e) {
    _pollFailCount++
    console.error(e)
    if (_pollFailCount >= 3) {
      stopPolling()
      stopGraphPolling()
      error.value = '与后端连接中断，请检查服务状态后重新提交'
      addLog(`Polling stopped after ${_pollFailCount} consecutive errors.`)
    }
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  addLog(`Loading full graph data: ${graphId}`)
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully.')
    } else {
      addLog(`Failed to load graph data: ${res.error}`)
    }
  } catch (e) {
    addLog(`Exception loading graph: ${e.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog('Manual graph refresh triggered.')
    loadGraph(projectData.value.graph_id)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer)
    graphPollTimer = null
    addLog('Graph polling stopped.')
  }
}

onMounted(() => {
  initProject()
})

onUnmounted(() => {
  stopPolling()
  stopGraphPolling()
  stopOntologyPolling()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #F0F2F7;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 2px solid #2E86AB;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFD 100%);
  z-index: 100;
  position: relative;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
  color: #2E86AB;
}

.view-switcher {
  display: flex;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: #000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
  min-width: 300px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #E0E0E0;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

@keyframes pulse { 50% { opacity: 0.5; } }

/* Action Buttons */
.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  border: none;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.pause-btn {
  background: #FF9800;
  color: white;
}

.pause-btn:hover {
  background: #F57C00;
}

.home-btn {
  background: #2E86AB;
  color: white;
}

.home-btn:hover {
  background: #1A5D7A;
}

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #EAEAEA;
}
</style>
