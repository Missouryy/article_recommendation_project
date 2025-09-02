<template>
  <div id="app" :class="{ 'dark': isDark }">
    <div class="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
      <nav class="bg-white dark:bg-gray-800 shadow-lg border-b border-gray-200 dark:border-gray-700 animate-fade-in">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="flex justify-between h-16">
            <div class="flex items-center">
              <router-link to="/" class="flex-shrink-0 flex items-center">
                <img src="@/assets/logo.png" alt="Logo" class="h-8 w-8 rounded-lg mr-3 shadow-md" />
                <span class="font-bold text-xl text-gray-900 dark:text-white">学术推荐</span>
              </router-link>
              
              <div class="hidden md:ml-10 md:flex md:space-x-8">
                 <a @click="handleNavReset('Search', '/search')" class="nav-link cursor-pointer">智能搜索</a>
                 <a @click="handleNavReset('Papers', '/papers')" class="nav-link cursor-pointer">论文库</a>
                 <router-link to="/authors" class="nav-link">学者库</router-link>
                 <router-link to="/workspace" class="nav-link">工作台</router-link>
               </div>
            </div>
            
            <div class="flex items-center space-x-4">
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
              
              <div v-if="userStore.isAuthenticated" class="relative">
                <button
                  @click="showUserMenu = !showUserMenu"
                  class="flex items-center text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <div class="h-8 w-8 rounded-full bg-gray-300 flex items-center justify-center text-gray-600 text-sm font-medium">
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
      
      <main class="flex-1">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <keep-alive :include="keepAliveInclude">
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </main>
      
      <div v-if="notification.show" class="fixed top-4 right-4 z-50">
        <div :class="notificationClasses" class="px-4 py-3 rounded-lg shadow-lg animate-scale-in">
          <p class="text-sm font-medium">{{ notification.message }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from './stores/user'
import { useThemeStore } from './stores/theme'

const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const showUserMenu = ref(false)
const notification = ref({
  show: false,
  message: '',
  type: 'success'
})

// 创建一个 ref 来动态控制 keep-alive 列表
const keepAliveInclude = ref(['Search', 'Papers'])

const isDark = computed(() => themeStore.isDark)

const notificationClasses = computed(() => ({
  'bg-green-500 text-white': notification.value.type === 'success',
  'bg-red-500 text-white': notification.value.type === 'error',
  'bg-yellow-500 text-white': notification.value.type === 'warning',
  'bg-blue-500 text-white': notification.value.type === 'info'
}))

const handleNavReset = async (componentName: string, path: string) => {
  keepAliveInclude.value = keepAliveInclude.value.filter(name => name !== componentName)
  await nextTick()

  if (!keepAliveInclude.value.includes(componentName)) {
    keepAliveInclude.value.push(componentName)
  }
  router.push(path)
}

const toggleDarkMode = () => {
  themeStore.toggleDarkMode()
}

const logout = async () => {
  await userStore.logout()
  showUserMenu.value = false
}

onMounted(() => {
  // 初始化用户状态
  userStore.initializeAuth()
})
</script>

<style lang="postcss" scoped>
.nav-link {
  @apply text-gray-500 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white px-3 py-2 rounded-md text-base font-semibold transition-colors;
}

.nav-link-lg {
  @apply text-lg font-bold;
}

.nav-link.router-link-active {
  @apply text-blue-600 dark:text-blue-400;
}

.btn-primary {
  @apply bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors dark:bg-blue-500 dark:hover:bg-blue-600 dark:text-white;
}

.btn-secondary {
  @apply bg-gray-200 hover:bg-gray-300 dark:bg-gray-600 dark:hover:bg-gray-500 text-gray-900 dark:text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors;
}
</style>