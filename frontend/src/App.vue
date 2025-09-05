<template>
  <div id="app" :class="{ 'dark': isDark }">
    <!-- 系统加载页面 - 只在初始加载且未导航时显示 -->
    <SystemLoading v-if="!systemReady && !hasNavigated" />
    
    <!-- 主应用 -->
    <div v-else class="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
      <!-- 导航栏 -->

      <nav class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-md shadow-soft border-b border-gray-200/60 dark:border-gray-700/60 animate-fade-in">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="flex justify-between h-16">
            <div class="flex items-center">
              <!-- Logo -->
              <router-link to="/" class="flex-shrink-0 flex items-center">
                <img src="@/assets/logo.png" alt="Logo" class="h-8 w-8 rounded-lg mr-3 shadow-md" />
                <span class="font-bold text-xl text-gray-900 dark:text-white">学术推荐</span>
              </router-link>
              
              <!-- 主导航 -->
              <div class="hidden md:ml-10 md:flex md:space-x-8">
                <router-link to="/search" class="nav-link">智能搜索</router-link>
                <router-link to="/papers" class="nav-link">论文库</router-link>
                <router-link to="/authors" class="nav-link">学者</router-link>
                <router-link to="/recommendations" class="nav-link">智能推荐</router-link>
                <router-link to="/workspace" class="nav-link">工作台</router-link>

              </div>
            </div>
            
            <div class="flex items-center space-x-4">
              <!-- 暗色模式切换 -->
              <button
                @click="toggleDarkMode"
                class="p-2 rounded-lg text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white transition-colors hover:bg-gray-100/60 dark:hover:bg-gray-700/60"
              >
                <svg v-if="isDark" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"></path>
                </svg>
                <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path>
                </svg>
              </button>
              
              <!-- 用户菜单 -->
              <div v-if="userStore.isAuthenticated" class="relative">
                <button
                  @click="showUserMenu = !showUserMenu"
                  class="flex items-center text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <!-- 修复：使用CSS生成的头像，不依赖图片文件 -->

                  <div class="h-8 w-8 rounded-full bg-gradient-to-r from-primary-600 to-accent-600 text-white flex items-center justify-center text-sm font-medium shadow-soft">
                    {{ userStore.userInitials || 'U' }}
                  </div>
                </button>
                
                <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-700 rounded-md shadow-lg py-1 z-50">
                  <router-link to="/profile" class="block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600">个人资料</router-link>
                  <router-link to="/workspace" class="block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600">我的工作台</router-link>
                  <button @click="logout" class="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600">退出登录</button>
                </div>
              </div>
              
              <div v-else class="flex space-x-2">
                <router-link to="/login" class="btn-secondary hover:-translate-y-0.5">登录</router-link>
                <router-link to="/register" class="btn-primary hover:-translate-y-0.5">注册</router-link>
              </div>
            </div>
          </div>
        </div>
      </nav>
      
      <!-- 主内容区域 -->
      <main class="flex-1">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
      
      <!-- 全局通知 -->
      <div v-if="notification.show" class="fixed top-4 right-4 z-50">
        <div :class="notificationClasses" class="px-4 py-3 rounded-lg shadow-medium animate-scale-in">
          <p class="text-sm font-medium">{{ notification.message }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useUserStore } from './stores/user'
import { useThemeStore } from './stores/theme'
import { useRoute } from 'vue-router'
import SystemLoading from './views/SystemLoading.vue'
import axios from 'axios'

const userStore = useUserStore()
const themeStore = useThemeStore()
const route = useRoute()

const systemReady = ref(false)
const hasNavigated = ref(false) // 标记用户是否已经导航到具体页面

const showUserMenu = ref(false)
const notification = ref({
  show: false,
  message: '',
  type: 'success'
})

const isDark = computed(() => themeStore.isDark)

const notificationClasses = computed(() => ({
  'bg-green-500 text-white': notification.value.type === 'success',
  'bg-red-500 text-white': notification.value.type === 'error',
  'bg-yellow-500 text-white': notification.value.type === 'warning',
  'bg-blue-500 text-white': notification.value.type === 'info'
}))

const toggleDarkMode = () => {
  themeStore.toggleDarkMode()
}

const logout = async () => {
  await userStore.logout()
  showUserMenu.value = false
}

// App级别的重试控制
let appRetryCount = 0
let appRetryDelay = 5000 // 5秒初始延迟
let statusCheckInterval: NodeJS.Timeout | null = null

const checkSystemStatus = async () => {
  // 如果系统已经准备好，停止检查
  if (systemReady.value) {
    if (statusCheckInterval) {
      clearTimeout(statusCheckInterval)
      statusCheckInterval = null
    }
    return
  }
  
  try {
    const response = await axios.get('/api/system/status', {
      timeout: 5000,
      params: { _t: Date.now() }
    })
    if (response.data.overall === 'ready') {
      systemReady.value = true
      // 系统准备好后，停止检查
      appRetryCount = 0
      appRetryDelay = 5000
      if (statusCheckInterval) {
        clearTimeout(statusCheckInterval)
        statusCheckInterval = null
      }
      return
    } else {
      // 如果系统未准备好，继续检查
      statusCheckInterval = setTimeout(checkSystemStatus, appRetryDelay)
    }
  } catch (error: any) {
    appRetryCount++
    
    // 静默处理连接错误，不在控制台输出
    if (error.code === 'ECONNREFUSED' || 
        error.message?.includes('ECONNREFUSED') || 
        error.response?.status === 503) {
      // 静默处理，使用指数退避
      if (appRetryCount > 3) {
        appRetryDelay = Math.min(appRetryDelay * 1.5, 15000) // 最大15秒
      }
    } else {
      console.error('App系统状态检查失败:', error)
      appRetryCount = 0
      appRetryDelay = 5000
    }
    statusCheckInterval = setTimeout(checkSystemStatus, appRetryDelay)
  }
}

// 监听路由变化，标记用户已导航
watch(() => route.path, (newPath) => {
  // 如果用户访问了具体页面（非根路径），标记为已导航
  if (newPath !== '/' && !hasNavigated.value) {
    hasNavigated.value = true
  }
}, { immediate: true })

onMounted(() => {
  // 检查系统状态
  checkSystemStatus()
  
  // 初始化用户状态
  userStore.initializeAuth()
})

// 组件卸载时清理定时器
onUnmounted(() => {
  if (statusCheckInterval) {
    clearTimeout(statusCheckInterval)
    statusCheckInterval = null
  }
})
</script>

<style scoped>
.nav-link {
  @apply text-gray-500 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors relative after:content-[''] after:absolute after:left-3 after:right-3 after:-bottom-0.5 after:h-0.5 after:bg-gradient-to-r after:from-primary-600 after:to-accent-600 after:rounded-full after:scale-x-0 hover:after:scale-x-100 after:origin-left after:transition-transform;
}

.nav-link.router-link-active {
  @apply text-primary-600 dark:text-primary-400;
}

.btn-primary {
  @apply bg-gradient-to-r from-primary-600 to-accent-600 hover:from-primary-700 hover:to-accent-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-soft active:scale-[0.99];
}

.btn-secondary {
  @apply bg-gray-200/80 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-white px-4 py-2 rounded-lg text-sm font-medium transition-all;
}
</style>