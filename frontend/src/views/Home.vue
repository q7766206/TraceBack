<template>
  <div class="home-container">
    <nav class="navbar">
      <div class="nav-brand">TRACEBACK</div>
      <div class="nav-links">
        <a href="#" class="settings-link" @click.prevent="showSettings = !showSettings">
          <span class="settings-icon">⚙</span> API 设置
        </a>
        <a href="#" class="github-link">溯·源 <span class="arrow">↗</span></a>
      </div>
    </nav>

    <!-- API 连接设置面板 -->
    <transition name="slide-down">
      <div v-if="showSettings" class="settings-overlay" @click.self="showSettings = false">
        <div class="settings-panel">
          <div class="settings-header">
            <h2>API 连接设置</h2>
            <button class="close-btn" @click="showSettings = false">✕</button>
          </div>

          <div class="settings-body">
            <!-- 主力模型 -->
            <div class="config-group">
              <div class="group-title">
                <span class="group-dot main"></span>
                主力模型（本体生成 / 图谱构建 / 报告生成）
              </div>
              <div class="config-row">
                <div class="config-field">
                  <label>平台</label>
                  <select v-model="mainProvider" @change="onMainProviderChange">
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="volces">火山引擎 (Volces)</option>
                    <option value="siliconflow">硅基流动 (SiliconFlow)</option>
                    <option value="alibaba">阿里云百炼</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>
                <div class="config-field">
                  <label>模型</label>
                  <select v-if="mainProvider !== 'custom' && modelOptions[mainProvider]" v-model="apiConfig.LLM_MODEL_NAME">
                    <option v-for="(m, idx) in modelOptions[mainProvider]" :key="m.value + idx" :value="m.value">{{ m.label }}</option>
                  </select>
                  <input v-else v-model="apiConfig.LLM_MODEL_NAME" placeholder="输入模型名称" />
                </div>
              </div>
              <div class="config-row">
                <div class="config-field full">
                  <label>API Key</label>
                  <input v-model="apiConfig.LLM_API_KEY" type="password" placeholder="sk-..." />
                </div>
              </div>
              <div v-if="mainProvider === 'custom'" class="config-row">
                <div class="config-field full">
                  <label>Base URL</label>
                  <input v-model="apiConfig.LLM_BASE_URL" placeholder="https://api.xxx.com/v1" />
                </div>
              </div>
            </div>

            <!-- 推理模型 -->
            <div class="config-group">
              <div class="group-title">
                <span class="group-dot reasoning"></span>
                推理模型（回溯分析 / 质证辩论）
              </div>
              <div class="config-row">
                <div class="config-field">
                  <label>平台</label>
                  <select v-model="reasoningProvider" @change="onReasoningProviderChange">
                    <option value="same">同主力模型</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="volces">火山引擎 (Volces)</option>
                    <option value="siliconflow">硅基流动 (SiliconFlow)</option>
                    <option value="alibaba">阿里云百炼</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>
                <div class="config-field">
                  <label>模型</label>
                  <select v-if="reasoningProvider !== 'custom' && reasoningProvider !== 'same' && modelOptions[reasoningProvider]" v-model="apiConfig.LLM_REASONING_MODEL_NAME">
                    <option v-for="(m, idx) in modelOptions[reasoningProvider]" :key="m.value + idx" :value="m.value">{{ m.label }}</option>
                  </select>
                  <input v-else v-model="apiConfig.LLM_REASONING_MODEL_NAME" :placeholder="reasoningProvider === 'same' ? '使用主力模型' : '输入模型名称'" />
                </div>
              </div>
              <div class="config-row">
                <div class="config-field full">
                  <label>API Key</label>
                  <input v-model="apiConfig.LLM_REASONING_API_KEY" type="password" placeholder="留空则使用主力模型Key" />
                </div>
              </div>
              <div v-if="reasoningProvider === 'custom'" class="config-row">
                <div class="config-field full">
                  <label>Base URL</label>
                  <input v-model="apiConfig.LLM_REASONING_BASE_URL" placeholder="https://api.xxx.com/v1" />
                </div>
              </div>
            </div>

            <!-- 轻量模型 -->
            <div class="config-group">
              <div class="group-title">
                <span class="group-dot fast"></span>
                轻量模型（高频抽取 / 图谱加速）
              </div>
              <div class="config-row">
                <div class="config-field">
                  <label>平台</label>
                  <select v-model="fastProvider" @change="onFastProviderChange">
                    <option value="same">同主力模型</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="volces">火山引擎 (Volces)</option>
                    <option value="siliconflow">硅基流动 (SiliconFlow)</option>
                    <option value="alibaba">阿里云百炼</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>
                <div class="config-field">
                  <label>模型</label>
                  <select v-if="fastProvider !== 'custom' && fastProvider !== 'same' && modelOptions[fastProvider]" v-model="apiConfig.LLM_FAST_MODEL_NAME">
                    <option v-for="(m, idx) in modelOptions[fastProvider]" :key="m.value + idx" :value="m.value">{{ m.label }}</option>
                  </select>
                  <input v-else v-model="apiConfig.LLM_FAST_MODEL_NAME" :placeholder="fastProvider === 'same' ? '使用主力模型' : '输入模型名称'" />
                </div>
              </div>
              <div class="config-row">
                <div class="config-field full">
                  <label>API Key</label>
                  <input v-model="apiConfig.LLM_FAST_API_KEY" type="password" placeholder="留空则使用主力模型Key" />
                </div>
              </div>
              <div v-if="fastProvider === 'custom'" class="config-row">
                <div class="config-field full">
                  <label>Base URL</label>
                  <input v-model="apiConfig.LLM_FAST_BASE_URL" placeholder="https://api.xxx.com/v1" />
                </div>
              </div>
            </div>

            <!-- 搜索引擎 -->
            <div class="config-group">
              <div class="group-title">
                <span class="group-dot search"></span>
                搜索引擎（可选，用于增强数据采集）
              </div>
              <div class="config-row">
                <div class="config-field">
                  <label>搜索引擎</label>
                  <select v-model="searchProvider">
                    <option value="duckduckgo">DuckDuckGo（免费，无需Key）</option>
                    <option value="bocha">Bocha</option>
                    <option value="tavily">Tavily</option>
                  </select>
                </div>
                <div class="config-field" v-if="searchProvider !== 'duckduckgo'">
                  <label>API Key</label>
                  <input v-model="apiConfig.SEARCH_API_KEY" type="password" placeholder="搜索引擎 API Key" />
                </div>
              </div>
            </div>

            <!-- Zep Cloud 知识图谱 -->
            <div class="config-group">
              <div class="group-title">
                <span class="group-dot zep"></span>
                Zep Cloud（知识图谱加速服务）
              </div>
              <div class="config-row">
                <div class="config-field full">
                  <label>API Key</label>
                  <input v-model="apiConfig.ZEP_API_KEY" type="password" placeholder="可选，用于知识图谱加速" />
                </div>
              </div>
            </div>
          </div>

          <div class="settings-footer">
            <div class="footer-left">
              <button class="btn-test" @click="testConnection" :disabled="testing">
                {{ testing ? '测试中...' : '测试连接' }}
              </button>
              <span v-if="testResult" class="test-result" :class="testResult.success ? 'ok' : 'fail'">
                {{ testResult.message }}
              </span>
            </div>
            <div class="footer-right">
              <button class="btn-cancel" @click="showSettings = false">取消</button>
              <button class="btn-save" @click="saveConfig" :disabled="saving">
                {{ saving ? '保存中...' : '保存配置' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <div class="main-content">
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">多智能体因果回溯分析引擎</span>
            <span class="version-text">/ v0.1-MVP</span>
          </div>
          
          <h1 class="main-title">
            上传任意资料<br>
            <span class="gradient-text">即刻回溯真相</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              即使只有一段文字，<span class="highlight-bold">TraceBack</span> 也能调度 <span class="highlight-orange">7 个专业 AI Agent</span> 协作完成数据采集、时间线重建、因果推理、质证辩论，输出带有完整证据链和置信度评估的 <span class="highlight-code">回溯分析报告</span>
            </p>
          </div>
        </div>
      </section>

      <!-- 上传区域 -->
      <section class="upload-section">
        <div class="upload-card">
          <div class="upload-header">
            <h2>开始回溯分析</h2>
            <p class="upload-subtitle">上传相关资料，描述你想回溯的问题</p>
          </div>
          
          <div class="form-group">
            <label>回溯分析需求 <span class="required">*</span></label>
            <textarea 
              v-model="analysisRequirement" 
              placeholder="例如：分析2024年某公司股价暴跌的根本原因，追溯关键决策链和外部因素..."
              rows="3"
            ></textarea>
          </div>

          <div class="form-group">
            <label>项目名称</label>
            <input v-model="projectName" placeholder="例如：XX事件因果分析" />
          </div>

          <div class="form-group">
            <label>上传文档</label>
            <div 
              class="drop-zone" 
              @dragover.prevent 
              @drop.prevent="handleDrop"
              @click="$refs.fileInput.click()"
            >
              <input ref="fileInput" type="file" multiple accept=".pdf,.txt,.md,.docx,.html" @change="handleFiles" hidden />
              <div v-if="files.length === 0" class="drop-hint">
                <span class="drop-icon">📄</span>
                <p>点击或拖拽文件到此处</p>
                <p class="drop-formats">支持 PDF、TXT、MD、DOCX、HTML</p>
              </div>
              <div v-else class="file-list">
                <div v-for="(f, i) in files" :key="i" class="file-item">
                  <span>{{ f.name }}</span>
                  <button @click.stop="removeFile(i)" class="remove-btn">×</button>
                </div>
              </div>
            </div>
          </div>

          <button 
            class="submit-btn" 
            :disabled="!canSubmit || loading"
            @click="submitProject"
          >
            {{ loading ? '处理中...' : '🔍 开始分析' }}
          </button>

          <div v-if="error" class="error-msg">{{ error }}</div>
        </div>
      </section>

      <!-- Agent 展示 -->
      <section class="agents-section">
        <h2>7 个专业 Agent 协作分析</h2>
        <div class="agents-grid">
          <div v-for="agent in agents" :key="agent.agent_id" class="agent-card" :style="{ borderColor: agent.color }">
            <span class="agent-icon">{{ agent.icon }}</span>
            <h3 :style="{ color: agent.color }">{{ agent.name_cn }}</h3>
            <p>{{ agent.role }}</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import api from '../api/index'
import { getAgents } from '../api/analysis'

export default {
  name: 'Home',
  data() {
    return {
      analysisRequirement: '',
      projectName: '',
      files: [],
      loading: false,
      error: '',
      agents: [],
      // API 设置相关
      showSettings: false,
      saving: false,
      testing: false,
      testResult: null,
      // 平台选择
      mainProvider: 'deepseek',
      reasoningProvider: 'same',
      fastProvider: 'same',
      // 搜索引擎
      searchProvider: 'duckduckgo',
      // 预置模型选项
      modelOptions: {
        openai: [
          { value: 'gpt-4o', label: 'GPT-4o' },
          { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
          { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
          { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
        ],
        anthropic: [
          { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
          { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
          { value: 'claude-3-sonnet-20240229', label: 'Claude 3 Sonnet' },
          { value: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku' },
        ],
        deepseek: [
          { value: 'deepseek-chat', label: 'DeepSeek Chat' },
          { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner' },
        ],
        volces: [
          { value: 'deepseek-v3-2-251201', label: 'DeepSeek V3' },
          { value: 'doubao-seed-2-0-pro-260215', label: '豆包 Seed Pro' },
          { value: 'doubao-seed-2-0-mini-260215', label: '豆包 Seed Mini' },
        ],
        siliconflow: [
          { value: 'deepseek-ai/DeepSeek-V3', label: 'DeepSeek V3' },
          { value: 'deepseek-ai/DeepSeek-R1', label: 'DeepSeek R1' },
          { value: 'Qwen/Qwen2.5-72B-Instruct', label: 'Qwen2.5 72B' },
          { value: 'meta-llama/Llama-3.3-70B-Instruct', label: 'Llama 3.3 70B' },
        ],
        openrouter: [
          { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
          { value: 'openai/gpt-4o', label: 'GPT-4o' },
          { value: 'deepseek/deepseek-chat', label: 'DeepSeek Chat' },
          { value: 'google/gemini-2.0-flash', label: 'Gemini Flash' },
        ],
        alibaba: [
          { value: 'qwen-max', label: '通义千问-Max' },
          { value: 'qwen-max-2025-01-25', label: '通义千问-Max-2025' },
          { value: 'qwen-plus', label: '通义千问-Plus' },
          { value: 'qwen-turbo', label: '通义千问-Turbo' },
          { value: 'qwen-long', label: '通义千问-Long' },
        ],
      },
      // API 配置
      apiConfig: {
        LLM_API_KEY: '',
        LLM_BASE_URL: '',
        LLM_MODEL_NAME: '',
        LLM_REASONING_API_KEY: '',
        LLM_REASONING_BASE_URL: '',
        LLM_REASONING_MODEL_NAME: '',
        LLM_FAST_API_KEY: '',
        LLM_FAST_BASE_URL: '',
        LLM_FAST_MODEL_NAME: '',
        SEARCH_API_KEY: '',
        ZEP_API_KEY: '',
      },
    }
  },
  computed: {
    canSubmit() {
      return this.analysisRequirement.trim().length > 0
    }
  },
  async mounted() {
    try {
      const res = await getAgents()
      if (res.success) {
        this.agents = res.data
      }
    } catch (e) {
      console.error('获取Agent信息失败:', e)
    }
    // 加载 API 配置
    try {
      const configRes = await api.get('/config/get')
      if (configRes.success) {
        Object.assign(this.apiConfig, configRes.data)
      }
    } catch (e) {
      console.error('获取API配置失败:', e)
    }
  },
  methods: {
    handleFiles(e) {
      this.files.push(...Array.from(e.target.files))
    },
    handleDrop(e) {
      this.files.push(...Array.from(e.dataTransfer.files))
    },
    removeFile(index) {
      this.files.splice(index, 1)
    },
    async submitProject() {
      this.loading = true
      this.error = ''
      try {
        const formData = new FormData()
        formData.append('simulation_requirement', this.analysisRequirement)
        formData.append('project_name', this.projectName || '回溯分析项目')
        for (const f of this.files) {
          formData.append('files', f)
        }

        const res = await api.post('/graph/ontology/generate', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 60000,
        })

        if (res.success) {
          const projectId = res.data.project_id
          // 异步模式：后端立即返回，前端立即跳转
          this.$router.push({ name: 'Process', params: { projectId } })
        } else {
          this.error = res.error || '提交失败'
        }
      } catch (e) {
        this.error = e.response?.data?.error || e.message || '网络错误'
      } finally {
        this.loading = false
      }
    },
    async saveConfig() {
      this.saving = true
      try {
        // 确保 Base URL 根据选择的平台正确设置
        const configToSave = { ...this.apiConfig }
        
        // 主力模型：如果不是自定义平台且 URL 为空，自动设置
        if (this.mainProvider !== 'custom' && !configToSave.LLM_BASE_URL) {
          configToSave.LLM_BASE_URL = this.getProviderBaseUrl(this.mainProvider)
        }
        
        // 推理模型：如果不是自定义或same且 URL 为空，自动设置
        if (this.reasoningProvider !== 'custom' && this.reasoningProvider !== 'same' && !configToSave.LLM_REASONING_BASE_URL) {
          configToSave.LLM_REASONING_BASE_URL = this.getProviderBaseUrl(this.reasoningProvider)
        }
        
        // 轻量模型：如果不是自定义或same且 URL 为空，自动设置
        if (this.fastProvider !== 'custom' && this.fastProvider !== 'same' && !configToSave.LLM_FAST_BASE_URL) {
          configToSave.LLM_FAST_BASE_URL = this.getProviderBaseUrl(this.fastProvider)
        }
        
        console.log('[SaveConfig] Saving config:', configToSave)
        const res = await api.post('/config/update', configToSave)
        if (res.success) {
          this.testResult = { success: true, message: res.message || '配置已保存' }
          setTimeout(() => { this.testResult = null }, 3000)
        } else {
          this.testResult = { success: false, message: res.error || '保存失败' }
        }
      } catch (e) {
        console.error('[SaveConfig] Error:', e)
        this.testResult = { success: false, message: e.message || '保存失败' }
      } finally {
        this.saving = false
      }
    },
    async testConnection() {
      this.testing = true
      this.testResult = null
      try {
        // 从 provider 自动获取 base_url
        const providerKey = this.mainProvider || 'volces'
        const baseUrl = this.getProviderBaseUrl(providerKey)
        const res = await api.post('/config/test', {
          base_url: baseUrl,
          api_key: this.apiConfig.LLM_API_KEY,
          model: this.apiConfig.LLM_MODEL_NAME,
        })
        this.testResult = {
          success: res.success,
          message: res.success ? '连接成功' : (res.error || '连接失败')
        }
      } catch (e) {
        this.testResult = { success: false, message: e.message || '连接失败' }
      } finally {
        this.testing = false
      }
    },
    // 平台 Base URL 映射
    getProviderBaseUrl(provider) {
      const urls = {
        openai: 'https://api.openai.com/v1',
        anthropic: 'https://api.anthropic.com/v1',
        deepseek: 'https://api.deepseek.com/v1',
        volces: 'https://ark.cn-beijing.volces.com/api/v3',
        siliconflow: 'https://api.siliconflow.cn/v1',
        openrouter: 'https://openrouter.ai/api/v1',
        alibaba: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      }
      return urls[provider] || ''
    },
    // 主力模型平台切换
    onMainProviderChange() {
      const p = this.mainProvider
      if (p === 'custom') {
        this.apiConfig.LLM_BASE_URL = ''
        this.apiConfig.LLM_MODEL_NAME = ''
      } else {
        this.apiConfig.LLM_BASE_URL = this.getProviderBaseUrl(p)
        // 默认选第一个模型
        const models = this.modelOptions[p]
        this.apiConfig.LLM_MODEL_NAME = models && models[0] ? models[0].value : ''
      }
    },
    // 推理模型平台切换
    onReasoningProviderChange() {
      const p = this.reasoningProvider
      if (p === 'same') {
        this.apiConfig.LLM_REASONING_BASE_URL = ''
        this.apiConfig.LLM_REASONING_MODEL_NAME = ''
        this.apiConfig.LLM_REASONING_API_KEY = ''
      } else if (p === 'custom') {
        this.apiConfig.LLM_REASONING_BASE_URL = ''
        this.apiConfig.LLM_REASONING_MODEL_NAME = ''
      } else {
        this.apiConfig.LLM_REASONING_BASE_URL = this.getProviderBaseUrl(p)
        const models = this.modelOptions[p]
        this.apiConfig.LLM_REASONING_MODEL_NAME = models && models[0] ? models[0].value : ''
      }
    },
    // 轻量模型平台切换
    onFastProviderChange() {
      const p = this.fastProvider
      if (p === 'same') {
        this.apiConfig.LLM_FAST_BASE_URL = ''
        this.apiConfig.LLM_FAST_MODEL_NAME = ''
        this.apiConfig.LLM_FAST_API_KEY = ''
      } else if (p === 'custom') {
        this.apiConfig.LLM_FAST_BASE_URL = ''
        this.apiConfig.LLM_FAST_MODEL_NAME = ''
      } else {
        this.apiConfig.LLM_FAST_BASE_URL = this.getProviderBaseUrl(p)
        const models = this.modelOptions[p]
        this.apiConfig.LLM_FAST_MODEL_NAME = models && models[0] ? models[0].value : ''
      }
    }
  }
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  background: #0F172A;
  color: #E2E8F0;
  font-family: 'Inter', -apple-system, sans-serif;
}

.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 40px;
  border-bottom: 1px solid #1E293B;
}
.nav-brand { font-size: 20px; font-weight: 800; color: #E8963E; letter-spacing: 2px; }
.github-link { color: #94A3B8; text-decoration: none; font-size: 14px; }
.arrow { font-size: 12px; }

.main-content { max-width: 960px; margin: 0 auto; padding: 40px 20px; }

.hero-section { margin-bottom: 48px; }
.tag-row { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.orange-tag { background: #E8963E; color: #fff; padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: 600; }
.version-text { color: #64748B; font-size: 13px; }

.main-title { font-size: 42px; font-weight: 800; line-height: 1.2; margin-bottom: 20px; }
.gradient-text { background: linear-gradient(135deg, #2E86AB, #E8963E); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

.hero-desc { font-size: 16px; line-height: 1.8; color: #94A3B8; max-width: 640px; }
.highlight-bold { color: #E8963E; font-weight: 700; }
.highlight-orange { color: #E8963E; }
.highlight-code { color: #2E86AB; font-weight: 600; }

.upload-section { margin-bottom: 60px; }
.upload-card { background: #1E293B; border-radius: 16px; padding: 32px; border: 1px solid #334155; }
.upload-header h2 { font-size: 22px; margin-bottom: 8px; }
.upload-subtitle { color: #64748B; font-size: 14px; }

.form-group { margin-top: 20px; }
.form-group label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 8px; color: #CBD5E1; }
.required { color: #E8963E; }

.form-group textarea, .form-group input {
  width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #334155;
  background: #0F172A; color: #E2E8F0; font-size: 14px; resize: vertical;
  box-sizing: border-box;
}
.form-group textarea:focus, .form-group input:focus { outline: none; border-color: #2E86AB; }

.drop-zone {
  border: 2px dashed #334155; border-radius: 12px; padding: 32px; text-align: center;
  cursor: pointer; transition: border-color 0.2s;
}
.drop-zone:hover { border-color: #2E86AB; }
.drop-icon { font-size: 32px; }
.drop-hint p { color: #64748B; margin: 8px 0 0; }
.drop-formats { font-size: 12px; color: #475569; }

.file-list { text-align: left; }
.file-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #0F172A; border-radius: 6px; margin-bottom: 6px; font-size: 13px; }
.remove-btn { background: none; border: none; color: #DC2626; cursor: pointer; font-size: 18px; }

.submit-btn {
  width: 100%; margin-top: 24px; padding: 14px; border: none; border-radius: 10px;
  background: linear-gradient(135deg, #2E86AB, #1B6D92); color: #fff; font-size: 16px;
  font-weight: 700; cursor: pointer; transition: opacity 0.2s;
}
.submit-btn:hover { opacity: 0.9; }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.error-msg { margin-top: 12px; color: #DC2626; font-size: 13px; text-align: center; }

.agents-section h2 { font-size: 22px; margin-bottom: 24px; text-align: center; }
.agents-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
.agent-card {
  background: #1E293B; border-radius: 12px; padding: 20px; border-left: 3px solid #334155;
  transition: transform 0.2s;
}
.agent-card:hover { transform: translateY(-2px); }
.agent-icon { font-size: 28px; }
.agent-card h3 { font-size: 15px; margin: 8px 0 4px; }
.agent-card p { font-size: 12px; color: #94A3B8; line-height: 1.5; }

/* Settings Link */
.nav-links { display: flex; align-items: center; gap: 16px; }
.settings-link { color: #94A3B8; text-decoration: none; font-size: 14px; cursor: pointer; transition: color 0.2s; display: flex; align-items: center; gap: 4px; }
.settings-link:hover { color: #E8963E; }
.settings-icon { font-size: 16px; }

/* Settings Panel Overlay */
.settings-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px);
  z-index: 1000; display: flex; align-items: center; justify-content: center;
}
.settings-panel {
  background: #1E293B; border-radius: 16px; width: 680px; max-height: 85vh;
  border: 1px solid #334155; display: flex; flex-direction: column;
  box-shadow: 0 24px 48px rgba(0,0,0,0.4);
}
.settings-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 24px; border-bottom: 1px solid #334155;
}
.settings-header h2 { font-size: 18px; font-weight: 700; color: #E2E8F0; }
.close-btn { background: none; border: none; color: #64748B; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 4px; }
.close-btn:hover { color: #E2E8F0; background: #334155; }

.settings-body { padding: 20px 24px; overflow-y: auto; flex: 1; }

.config-group { margin-bottom: 20px; }
.group-title {
  font-size: 13px; font-weight: 600; color: #CBD5E1; margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.group-dot { width: 8px; height: 8px; border-radius: 50%; }
.group-dot.main { background: #2E86AB; }
.group-dot.reasoning { background: #E8963E; }
.group-dot.fast { background: #22C55E; }
.group-dot.search { background: #A855F7; }
.group-dot.zep { background: #F59E0B; }

/* 搜索引擎样式 */
.search-provider-select { width: 100%; }
.search-api-field { transition: opacity 0.2s; }

.config-row { display: flex; gap: 12px; margin-bottom: 8px; }
.config-field { flex: 1; }
.config-field.full { flex: 1; }
.config-field label { display: block; font-size: 11px; color: #64748B; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.config-field input, .config-field select {
  width: 100%; padding: 8px 12px; border-radius: 6px; border: 1px solid #334155;
  background: #0F172A; color: #E2E8F0; font-size: 13px; font-family: 'JetBrains Mono', monospace;
  box-sizing: border-box;
}
.config-field input:focus, .config-field select:focus { outline: none; border-color: #2E86AB; }
.config-field select { cursor: pointer; }

.settings-footer {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; border-top: 1px solid #334155;
}
.footer-left { display: flex; align-items: center; gap: 12px; }
.footer-right { display: flex; gap: 8px; }

.btn-test {
  padding: 8px 16px; border: 1px solid #334155; border-radius: 6px;
  background: transparent; color: #94A3B8; font-size: 13px; cursor: pointer;
}
.btn-test:hover { border-color: #2E86AB; color: #2E86AB; }
.btn-test:disabled { opacity: 0.5; cursor: not-allowed; }

.test-result { font-size: 12px; }
.test-result.ok { color: #22C55E; }
.test-result.fail { color: #DC2626; }

.btn-cancel {
  padding: 8px 16px; border: 1px solid #334155; border-radius: 6px;
  background: transparent; color: #94A3B8; font-size: 13px; cursor: pointer;
}
.btn-cancel:hover { background: #334155; }

.btn-save {
  padding: 8px 20px; border: none; border-radius: 6px;
  background: linear-gradient(135deg, #2E86AB, #1B6D92); color: #fff;
  font-size: 13px; font-weight: 600; cursor: pointer;
}
.btn-save:hover { opacity: 0.9; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

/* Slide transition */
.slide-down-enter-active, .slide-down-leave-active { transition: opacity 0.25s ease; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; }
</style>
