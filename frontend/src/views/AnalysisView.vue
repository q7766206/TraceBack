<template>
  <div class="analysis-view">
    <!-- 顶部状态栏 -->
    <div class="top-bar">
      <div class="status-info">
        <span class="analysis-id">{{ analysisId }}</span>
        <span class="phase-badge" :class="currentPhase">{{ phaseLabel }}</span>
        <span class="confidence-badge" v-if="overallConfidence > 0">
          置信度: {{ (overallConfidence * 100).toFixed(0) }}%
        </span>
      </div>
      <div class="controls">
        <button v-if="!isRunning" class="btn-start" @click="startAnalysis">▶ 开始分析</button>
        <button v-else class="btn-stop" @click="stopAnalysis">⏹ 停止</button>
      </div>
    </div>

    <!-- 主内容区：左右分栏 -->
    <div class="main-content">
      <!-- 左侧：因果网络图 + 时间线 -->
      <div class="left-panel">
        <div class="causal-graph-container">
          <div class="panel-header">
            <span class="panel-title">因果网络图</span>
            <span class="node-count">{{ causalNodes.length }} 节点 / {{ causalEdges.length }} 边</span>
          </div>
          <svg ref="causalSvg" class="causal-svg"></svg>
        </div>
        <div class="timeline-container">
          <div class="panel-header">
            <span class="panel-title">事件时间线</span>
          </div>
          <svg ref="timelineSvg" class="timeline-svg"></svg>
        </div>
      </div>

      <!-- 右侧：Agent质证面板 -->
      <div class="right-panel">
        <div class="panel-header">
          <span class="panel-title">质证辩论</span>
          <span class="msg-count">{{ debateMessages.length }} 条消息</span>
        </div>
        <div class="debate-messages" ref="debateContainer">
          <div
            v-for="msg in debateMessages"
            :key="msg.message_id"
            class="debate-msg"
            :class="msg.message_type"
          >
            <div class="msg-header">
              <span class="agent-icon">{{ msg.agent_icon }}</span>
              <span class="agent-name" :style="{ color: msg.agent_color }">{{ msg.agent_name }}</span>
              <span class="msg-type-badge" :class="msg.message_type">{{ msgTypeLabel(msg.message_type) }}</span>
              <span class="msg-confidence" v-if="msg.confidence > 0">{{ (msg.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div class="msg-content" v-html="renderMarkdown(msg.content)"></div>
          </div>
          <div v-if="debateMessages.length === 0" class="empty-state">
            等待分析启动...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import * as d3 from 'd3'
import { getAnalysisStatus, getCausalGraph, getDebateMessages, startAnalysis as apiStart, stopAnalysis as apiStop } from '../api/analysis'

export default {
  name: 'AnalysisView',
  props: ['analysisId'],
  data() {
    return {
      status: 'created',
      currentPhase: 'created',
      overallConfidence: 0,
      causalNodes: [],
      causalEdges: [],
      debateMessages: [],
      isRunning: false,
      pollTimer: null,
      debatePollTimer: null,
      nextDebateIndex: 0,
    }
  },
  computed: {
    phaseLabel() {
      const labels = {
        created: '等待启动',
        data_collection: '📡 数据采集中',
        timeline_building: '⏳ 时间线重建中',
        causal_reasoning: '🔎 因果推理中',
        evidence_audit: '📋 证据审计中',
        debate: '🏛️ 质证辩论中',
        consensus: '✅ 共识形成中',
        report_generation: '📝 报告生成中',
        completed: '✅ 分析完成',
        failed: '❌ 分析失败',
      }
      return labels[this.currentPhase] || this.currentPhase
    }
  },
  mounted() {
    this.fetchStatus()
  },
  beforeUnmount() {
    this.clearPolling()
  },
  methods: {
    async fetchStatus() {
      try {
        const res = await getAnalysisStatus(this.analysisId)
        if (res.success) {
          const data = res.data
          this.status = data.status
          this.currentPhase = data.current_phase
          this.overallConfidence = data.overall_confidence
          this.isRunning = data.status === 'running'
        }
      } catch (e) {
        console.error('获取状态失败:', e)
      }
    },
    async startAnalysis() {
      try {
        await apiStart(this.analysisId)
        this.isRunning = true
        this.startPolling()
      } catch (e) {
        console.error('启动失败:', e)
      }
    },
    async stopAnalysis() {
      try {
        await apiStop(this.analysisId)
        this.isRunning = false
        this.clearPolling()
      } catch (e) {
        console.error('停止失败:', e)
      }
    },
    startPolling() {
      this.pollTimer = setInterval(async () => {
        await this.fetchStatus()
        await this.fetchCausalGraph()
        if (!this.isRunning) this.clearPolling()
      }, 3000)
      this.debatePollTimer = setInterval(async () => {
        await this.fetchDebateMessages()
      }, 2000)
    },
    clearPolling() {
      if (this.pollTimer) clearInterval(this.pollTimer)
      if (this.debatePollTimer) clearInterval(this.debatePollTimer)
    },
    async fetchCausalGraph() {
      try {
        const res = await getCausalGraph(this.analysisId)
        if (res.success) {
          this.causalNodes = res.data.nodes || []
          this.causalEdges = res.data.edges || []
          this.renderCausalGraph()
        }
      } catch (e) { /* ignore */ }
    },
    async fetchDebateMessages() {
      try {
        const res = await getDebateMessages(this.analysisId, this.nextDebateIndex)
        if (res.success && res.data.length > 0) {
          this.debateMessages.push(...res.data)
          this.nextDebateIndex = res.next_index
          this.$nextTick(() => {
            const container = this.$refs.debateContainer
            if (container) container.scrollTop = container.scrollHeight
          })
        }
      } catch (e) { /* ignore */ }
    },
    renderCausalGraph() {
      const svg = d3.select(this.$refs.causalSvg)
      svg.selectAll('*').remove()

      if (this.causalNodes.length === 0) return

      const width = this.$refs.causalSvg?.clientWidth || 600
      const height = this.$refs.causalSvg?.clientHeight || 400

      // 箭头定义
      svg.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20).attr('refY', 0)
        .attr('markerWidth', 8).attr('markerHeight', 8)
        .attr('orient', 'auto')
        .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#6B7280')

      const g = svg.append('g')

      // 缩放
      svg.call(d3.zoom().scaleExtent([0.3, 3]).on('zoom', (e) => g.attr('transform', e.transform)))

      // 力导向模拟
      const simulation = d3.forceSimulation(this.causalNodes)
        .force('link', d3.forceLink(this.causalEdges).id(d => d.id).distance(120))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide(40))

      // 边
      const link = g.selectAll('.link')
        .data(this.causalEdges).enter().append('line')
        .attr('class', 'link')
        .attr('stroke', d => this.getCausalColor(d.causal_type))
        .attr('stroke-width', d => Math.max(1, (d.strength || 0.5) * 4))
        .attr('stroke-opacity', 0.6)
        .attr('marker-end', 'url(#arrowhead)')

      // 节点
      const node = g.selectAll('.node')
        .data(this.causalNodes).enter().append('g')
        .attr('class', 'node')
        .call(d3.drag()
          .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
          .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
          .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null })
        )

      node.append('rect')
        .attr('width', 100).attr('height', 36).attr('rx', 6).attr('ry', 6)
        .attr('x', -50).attr('y', -18)
        .attr('fill', d => this.getConfidenceColor(d.credibility_score))
        .attr('stroke', d => this.getConfidenceBorder(d.credibility_score))
        .attr('stroke-width', 2)

      node.append('text')
        .attr('text-anchor', 'middle').attr('dy', 4).attr('font-size', 11).attr('fill', '#fff')
        .text(d => (d.name || '').substring(0, 10))

      simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
        node.attr('transform', d => `translate(${d.x},${d.y})`)
      })
    },
    getCausalColor(type) {
      const colors = { direct: '#2E86AB', indirect: '#7C3AED', root: '#DC2626', temporal: '#6B7280', evidential: '#059669' }
      return colors[type] || '#6B7280'
    },
    getConfidenceColor(score) {
      if (score >= 0.8) return '#059669'
      if (score >= 0.6) return '#D97706'
      if (score >= 0.3) return '#EA580C'
      return '#DC2626'
    },
    getConfidenceBorder(score) {
      if (score >= 0.8) return '#047857'
      if (score >= 0.6) return '#B45309'
      if (score >= 0.3) return '#C2410C'
      return '#B91C1C'
    },
    msgTypeLabel(type) {
      const labels = { hypothesis: '假设', challenge: '质疑', evidence: '证据', consensus: '共识', question: '提问' }
      return labels[type] || type
    },
    renderMarkdown(text) {
      // 简单Markdown渲染
      return (text || '')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        .replace(/- (.*?)(?=<br>|$)/g, '&bull; $1')
    }
  }
}
</script>

<style scoped>
.analysis-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0F172A;
  color: #E2E8F0;
  font-family: 'Inter', -apple-system, sans-serif;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #1E293B;
  border-bottom: 1px solid #334155;
}

.status-info { display: flex; align-items: center; gap: 12px; }
.analysis-id { font-family: monospace; font-size: 12px; color: #64748B; }
.phase-badge { padding: 4px 12px; border-radius: 12px; font-size: 13px; background: #1B3A5C; }
.phase-badge.completed { background: #059669; }
.phase-badge.failed { background: #DC2626; }
.phase-badge.debate { background: #E8963E; }
.confidence-badge { padding: 4px 10px; border-radius: 8px; font-size: 12px; background: #334155; }

.btn-start { padding: 8px 20px; border: none; border-radius: 8px; background: #2E86AB; color: #fff; cursor: pointer; font-size: 14px; }
.btn-start:hover { background: #247A9E; }
.btn-stop { padding: 8px 20px; border: none; border-radius: 8px; background: #DC2626; color: #fff; cursor: pointer; font-size: 14px; }

.main-content { flex: 1; display: flex; overflow: hidden; }

.left-panel { flex: 1; display: flex; flex-direction: column; border-right: 1px solid #334155; }
.causal-graph-container { flex: 2; display: flex; flex-direction: column; }
.timeline-container { flex: 1; border-top: 1px solid #334155; display: flex; flex-direction: column; }

.right-panel { width: 420px; display: flex; flex-direction: column; }

.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 16px; background: #1E293B; border-bottom: 1px solid #334155;
}
.panel-title { font-size: 14px; font-weight: 600; color: #E2E8F0; }
.node-count, .msg-count { font-size: 11px; color: #64748B; }

.causal-svg, .timeline-svg { flex: 1; width: 100%; }

.debate-messages { flex: 1; overflow-y: auto; padding: 12px; }

.debate-msg {
  margin-bottom: 12px; padding: 12px; border-radius: 8px;
  background: #1E293B; border-left: 3px solid #334155;
}
.debate-msg.hypothesis { border-left-color: #DC2626; }
.debate-msg.challenge { border-left-color: #991B1B; }
.debate-msg.evidence { border-left-color: #2E86AB; }
.debate-msg.consensus { border-left-color: #E8963E; }

.msg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.agent-icon { font-size: 18px; }
.agent-name { font-weight: 600; font-size: 13px; }
.msg-type-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #334155; }
.msg-type-badge.challenge { background: #7F1D1D; color: #FCA5A5; }
.msg-type-badge.hypothesis { background: #7F1D1D; color: #FCA5A5; }
.msg-type-badge.consensus { background: #78350F; color: #FCD34D; }
.msg-confidence { font-size: 11px; color: #64748B; margin-left: auto; }

.msg-content { font-size: 13px; line-height: 1.6; color: #CBD5E1; }

.empty-state { text-align: center; padding: 60px 20px; color: #64748B; font-size: 14px; }
</style>
