<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center">
    <div class="max-w-md w-full mx-4">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8 text-center">
        <!-- Logo和标题 -->
        <div class="mb-8">
          <div class="w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl mx-auto mb-4 flex items-center justify-center">
            <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
            </svg>
          </div>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">学术推荐系统</h1>
          <p class="text-gray-600 dark:text-gray-400">正在初始化智能推荐引擎...</p>
        </div>

        <!-- 进度条 -->
        <div class="mb-6">
          <div class="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
            <span>加载进度</span>
            <span>{{ progress }}%</span>
          </div>
          <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div 
              class="bg-gradient-to-r from-blue-600 to-purple-600 h-2 rounded-full transition-all duration-500 ease-out"
              :style="{ width: progress + '%' }"
            ></div>
          </div>
        </div>

        <!-- 当前状态 -->
        <div class="space-y-3 mb-6">
          <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div class="flex items-center space-x-3">
              <div :class="statusIcons.database" class="w-2 h-2 rounded-full"></div>
              <span class="text-sm text-gray-700 dark:text-gray-300">数据库连接</span>
            </div>
            <span class="text-xs text-gray-500 dark:text-gray-400">{{ statusTexts.database }}</span>
          </div>
          
          <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div class="flex items-center space-x-3">
              <div :class="statusIcons.faiss_index" class="w-2 h-2 rounded-full"></div>
              <span class="text-sm text-gray-700 dark:text-gray-300">向量索引</span>
            </div>
            <span class="text-xs text-gray-500 dark:text-gray-400">{{ statusTexts.faiss_index }}</span>
          </div>
          
          <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div class="flex items-center space-x-3">
              <div :class="statusIcons.bert_model" class="w-2 h-2 rounded-full"></div>
              <span class="text-sm text-gray-700 dark:text-gray-300">AI模型</span>
            </div>
            <span class="text-xs text-gray-500 dark:text-gray-400">{{ statusTexts.bert_model }}</span>
          </div>
          
        </div>

        <!-- 加载提示 -->
        <div class="text-center">
          <div v-if="!error" class="flex items-center justify-center space-x-2 text-gray-600 dark:text-gray-400">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span class="text-sm">{{ currentStep }}</span>
          </div>
          
          <div v-if="error" class="text-red-600 dark:text-red-400">
            <p class="text-sm mb-3">{{ error }}</p>
            <button 
              @click="checkStatus" 
              class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
            >
              重新检查
            </button>
          </div>
        </div>

        <!-- 详细提示信息 -->
        <div v-if="!error && progress < 100" class="mt-6 text-xs text-gray-500 dark:text-gray-400 space-y-2">
          <div v-if="systemStatus.overall === 'waiting'" class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
            <div class="flex items-center space-x-2">
              <div class="animate-spin rounded-full h-3 w-3 border-b border-blue-600"></div>
              <span class="text-blue-700 dark:text-blue-300 font-medium">等待后端服务启动</span>
            </div>
            <p class="mt-1 text-blue-600 dark:text-blue-400 text-xs">
              请确保后端服务已启动。如果是首次运行，后端初始化可能需要1-2分钟。
            </p>
          </div>
          <div v-else-if="systemStatus.overall === 'loading'" class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
            <div class="flex items-center space-x-2">
              <div class="animate-spin rounded-full h-3 w-3 border-b border-green-600"></div>
              <span class="text-green-700 dark:text-green-300 font-medium">正在加载智能推荐系统</span>
            </div>
            <p class="mt-1 text-green-600 dark:text-green-400 text-xs">
              正在加载FAISS向量索引和BERT模型，这可能需要30-60秒...
            </p>
          </div>
          <div v-else>
            <p>首次加载需要较长时间，请耐心等待</p>
            <p>预计还需 {{ estimatedTime }} 秒</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const systemStatus = ref({
  database: 'not_loaded',
  faiss_index: 'not_loaded', 
  bert_model: 'not_loaded',
  overall: 'initializing'
})

const progress = ref(0)
const error = ref('')
const startTime = ref(Date.now())
const checkInterval = ref<NodeJS.Timeout | null>(null)

const statusIcons = computed(() => ({
  database: systemStatus.value.database === 'ready' ? 'bg-green-500' : 
            systemStatus.value.database === 'error' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse',
  faiss_index: systemStatus.value.faiss_index === 'ready' ? 'bg-green-500' : 
               systemStatus.value.faiss_index === 'error' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse',
  bert_model: systemStatus.value.bert_model === 'ready' ? 'bg-green-500' : 
              systemStatus.value.bert_model === 'error' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
}))

const statusTexts = computed(() => ({
  database: systemStatus.value.database === 'ready' ? '已连接' : 
            systemStatus.value.database === 'error' ? '连接失败' : '连接中...',
  faiss_index: systemStatus.value.faiss_index === 'ready' ? '已加载' : 
               systemStatus.value.faiss_index === 'error' ? '加载失败' : '加载中...',
  bert_model: systemStatus.value.bert_model === 'ready' ? '已加载' : 
              systemStatus.value.bert_model === 'error' ? '加载失败' : '加载中...'
}))

const currentStep = computed(() => {
  if (systemStatus.value.overall === 'waiting') {
    if (retryCount.value === 0) {
      return '正在连接后端服务...'
    } else if (retryCount.value < 5) {
      return '正在等待后端服务启动...'
    } else {
      return '后端服务启动中，请稍等...'
    }
  }
  if (systemStatus.value.overall === 'loading') {
    if (systemStatus.value.faiss_index === 'loading') return '正在加载向量索引...'
    if (systemStatus.value.bert_model === 'loading') return '正在加载AI模型...'
    return '正在初始化智能推荐系统...'
  }
  if (systemStatus.value.database !== 'ready') return '正在连接数据库...'
  if (systemStatus.value.faiss_index !== 'ready') return '正在加载向量索引...'
  if (systemStatus.value.bert_model !== 'ready') return '正在加载AI模型...'
  return '初始化完成！'
})

const estimatedTime = computed(() => {
  const elapsed = (Date.now() - startTime.value) / 1000
  const totalEstimated = 60 // 预计总共60秒
  const remaining = Math.max(0, totalEstimated - elapsed)
  return Math.ceil(remaining)
})

// 重试计数器和延迟控制
const retryCount = ref(0)
const retryDelay = ref(2000) // 初始2秒
const maxRetryDelay = ref(10000) // 最大10秒
const backendStartupDetected = ref(false)
const consecutiveErrors = ref(0) // 连续错误计数
const isChecking = ref(false) // 防止重复检查
const debugMode = ref(false) // 调试模式，可以通过URL参数控制

const checkStatus = async () => {
  // 防止重复检查
  if (isChecking.value) {
    if (debugMode.value) console.log('🔍 状态检查已在进行中，跳过重复请求')
    return
  }
  
  isChecking.value = true
  
  try {
    if (debugMode.value) {
      console.log(`🔍 开始检查系统状态 (第${retryCount.value + 1}次尝试，延迟${retryDelay.value}ms)`)
    }
    
    const response = await axios.get('/api/system/status', {
      timeout: 5000, // 5秒超时
      // 添加时间戳避免缓存
      params: { _t: Date.now() }
    })
    const data = response.data
    
    if (debugMode.value) {
      console.log('✅ 后端连接成功，系统状态:', data)
    }
    
    // 后端连接成功，重置重试参数
    retryCount.value = 0
    retryDelay.value = 2000
    backendStartupDetected.value = true
    consecutiveErrors.value = 0
    
    // 重置检查状态，允许后续检查
    isChecking.value = false
    
    // 更新系统状态 - 从API响应的components字段中获取
    systemStatus.value = {
      database: data.components?.database?.status || 'not_loaded',
      faiss_index: data.components?.faiss_index?.status || 'not_loaded',
      bert_model: data.components?.bert_model?.status || 'not_loaded',
      overall: data.overall || 'loading'
    }
    
    // 使用API返回的progress或计算进度
    if (data.progress !== undefined) {
      progress.value = data.progress
    } else {
      let progressValue = 10 // 后端连接成功基础10%
      if (systemStatus.value.database === 'ready') progressValue += 20
      if (systemStatus.value.faiss_index === 'ready') progressValue += 35
      if (systemStatus.value.bert_model === 'ready') progressValue += 35
      progress.value = progressValue
    }
    
    // 如果全部加载完成，跳转到主页（仅在初始加载时）
    if (systemStatus.value.overall === 'ready') {
      progress.value = 100
      if (debugMode.value) {
        console.log('🎉 系统完全加载完成，准备跳转')
      }
      
      // 通知App组件系统已准备就绪
      window.dispatchEvent(new CustomEvent('systemReady'))
      
      // 延迟一点时间让App组件更新状态
      setTimeout(() => {
        // 只有在根路径或特定加载页面时才跳转，避免在论文详情等页面时跳转
        const currentPath = window.location.pathname
        const isInitialLoad = currentPath === '/' || 
                             currentPath === '/loading' || 
                             currentPath === '/search' ||
                             currentPath === '/papers' ||
                             currentPath === '/authors' ||
                             currentPath === '/recommendations'
        
        if (isInitialLoad) {
          if (debugMode.value) {
            console.log('🚀 系统加载完成，准备跳转到主页')
          }
          
          // 直接跳转到主页
          router.push('/').then(() => {
            if (debugMode.value) {
              console.log('✅ 跳转到主页完成')
            }
          }).catch((error) => {
            if (debugMode.value) {
              console.error('❌ 跳转失败，使用强制刷新:', error)
            }
            // 如果路由跳转失败，强制刷新页面
            window.location.href = '/'
          })
        }
      }, 500) // 减少延迟时间
    } else {
      // 如果系统还在加载中，设置一个较长的延迟再次检查
      if (debugMode.value) {
        console.log('⏳ 系统仍在加载中，5秒后再次检查')
      }
      setTimeout(() => {
        if (!isChecking.value) {
          checkStatus()
        }
      }, 5000)
    }
    
    error.value = ''
  } catch (err: any) {
    retryCount.value++
    consecutiveErrors.value++
    
    // 设置默认的等待状态，让进度条显示等待后端启动
    systemStatus.value = {
      database: 'not_loaded',
      faiss_index: 'not_loaded', 
      bert_model: 'not_loaded',
      overall: 'waiting'
    }
    
    // 显示基础进度（等待后端启动）
    progress.value = backendStartupDetected.value ? 10 : 5
    
    // 对于连接错误，完全静默处理
    if (err.code === 'ECONNREFUSED' || 
        err.code === 'ETIMEDOUT' ||
        err.message?.includes('ECONNREFUSED') || 
        err.message?.includes('ETIMEDOUT') ||
        err.message?.includes('Network Error') ||
        err.message?.includes('timeout') ||
        err.response?.status === 503 ||
        err.response?.status === undefined) {
      
      if (debugMode.value) {
        console.log(`❌ 后端连接失败 (第${consecutiveErrors.value}次连续错误):`, err.message)
      }
      
      // 使用更激进的指数退避算法
      if (consecutiveErrors.value > 2) {
        retryDelay.value = Math.min(
          retryDelay.value * 1.5, 
          maxRetryDelay.value
        )
        if (debugMode.value) {
          console.log(`⏰ 调整重试延迟为: ${retryDelay.value}ms`)
        }
      }
      
      // 如果连续错误太多，进一步增加延迟
      if (consecutiveErrors.value > 8) {
        retryDelay.value = maxRetryDelay.value
        if (debugMode.value) {
          console.log(`⏰ 达到最大重试延迟: ${retryDelay.value}ms`)
        }
      }
    } else {
      // 其他类型的错误才显示给用户
      console.error('系统状态检查失败:', err)
      error.value = `检查系统状态失败: ${err.message}`
      consecutiveErrors.value = 0 // 重置连续错误计数
    }
    
    // 使用动态延迟重试
    if (debugMode.value) {
      console.log(`⏳ ${retryDelay.value}ms后重试...`)
    }
    setTimeout(() => {
      isChecking.value = false
      checkStatus()
    }, retryDelay.value)
  } finally {
    // 确保在finally中重置检查状态
    if (!isChecking.value) {
      isChecking.value = false
    }
  }
}

onMounted(() => {
  // 检查URL参数是否启用调试模式
  const urlParams = new URLSearchParams(window.location.search)
  debugMode.value = urlParams.get('debug') === 'true'
  
  if (debugMode.value) {
    console.log('🐛 调试模式已启用')
  }
  
  // 立即检查一次
  checkStatus()
  
  // 不再使用定时器，完全依赖重试机制
  // checkInterval.value = setInterval(checkStatus, 2000)
})

onUnmounted(() => {
  if (checkInterval.value) {
    clearInterval(checkInterval.value)
  }
  // 清理重试定时器
  isChecking.value = false
})
</script>

<style scoped>
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>
