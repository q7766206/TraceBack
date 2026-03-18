<template>
  <div class="license-container">
    <div class="license-card">
      <h1>TraceBack 溯·源</h1>
      <h2>请输入邀请码</h2>
      <div class="form-group">
        <input 
          type="text" 
          v-model="licenseKey" 
          placeholder="例如: RT3Z-FA8D-BR1M-18OK"
          class="license-input"
        />
      </div>
      <button @click="validateLicense" class="submit-button">
        验证邀请码
      </button>
      <div v-if="message" class="message" :class="messageType">
        {{ message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'

const router = useRouter()
const licenseKey = ref('')
const message = ref('')
const messageType = ref('')
const machineId = ref('')

// 获取机器ID
const getMachineId = () => {
  // 生成基于浏览器和系统信息的唯一标识
  const navigatorInfo = navigator.userAgent + navigator.platform + navigator.language
  const screenInfo = screen.width + 'x' + screen.height + '-' + screen.colorDepth
  const machineInfo = navigatorInfo + screenInfo
  
  // 简单的哈希函数生成机器ID
  let hash = 0
  for (let i = 0; i < machineInfo.length; i++) {
    const char = machineInfo.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // 转换为32位整数
  }
  
  return Math.abs(hash).toString(16)
}

onMounted(() => {
  machineId.value = getMachineId()
})

const validateLicense = async () => {
  if (!licenseKey.value) {
    message.value = '请输入邀请码'
    messageType.value = 'error'
    return
  }

  try {
    const response = await axios.post('/api/license/validate', {
      license_key: licenseKey.value,
      machine_id: machineId.value
    })

    if (response.data.valid) {
      localStorage.setItem('license_valid', 'true')
      localStorage.setItem('license_key', licenseKey.value)
      localStorage.setItem('machine_id', machineId.value)
      message.value = '邀请码验证成功！'
      messageType.value = 'success'
      setTimeout(() => {
        router.push('/')
      }, 1000)
    } else {
      message.value = response.data.message || '邀请码无效或已被使用'
      messageType.value = 'error'
    }
  } catch (error) {
    message.value = '验证失败，请稍后重试'
    messageType.value = 'error'
    console.error('验证失败:', error)
  }
}
</script>

<style scoped>
.license-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #ffffff;
}

.license-card {
  background-color: #f8f9fa;
  padding: 40px;
  border-radius: 10px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  width: 400px;
  text-align: center;
}

h1 {
  font-size: 24px;
  margin-bottom: 10px;
  color: #000000;
}

h2 {
  font-size: 18px;
  margin-bottom: 30px;
  color: #666666;
}

.form-group {
  margin-bottom: 20px;
}

.license-input {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  border: 1px solid #ddd;
  border-radius: 5px;
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
}

.submit-button {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  background-color: #000000;
  color: #ffffff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.submit-button:hover {
  background-color: #333333;
}

.message {
  margin-top: 20px;
  padding: 10px;
  border-radius: 5px;
  font-size: 14px;
}

.success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.error {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}
</style>