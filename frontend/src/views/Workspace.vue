<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">个人工作台</h1>
        <p class="text-gray-600 dark:text-gray-300">管理您的学术研究资料</p>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
        <div class="card p-6 text-center">
          <div class="text-2xl font-bold text-blue-600 dark:text-blue-400 mb-2">
            <span v-if="!loading">{{ stats.total_bookmarks }}</span>
            <div v-else class="animate-pulse bg-gray-300 dark:bg-gray-600 h-8 w-8 mx-auto rounded"></div>
          </div>
          <div class="text-sm text-gray-500">收藏论文</div>
        </div>
        <div class="card p-6 text-center">
          <div class="text-2xl font-bold text-green-600 dark:text-green-400 mb-2">
            <span v-if="!loading">{{ stats.total_folders }}</span>
            <div v-else class="animate-pulse bg-gray-300 dark:bg-gray-600 h-8 w-8 mx-auto rounded"></div>
          </div>
          <div class="text-sm text-gray-500">收藏夹</div>
        </div>
        <div class="card p-6 text-center">
          <div class="text-2xl font-bold text-purple-600 dark:text-purple-400 mb-2">
            <span v-if="!loading">{{ stats.followed_authors_count }}</span>
            <div v-else class="animate-pulse bg-gray-300 dark:bg-gray-600 h-8 w-8 mx-auto rounded"></div>
          </div>
          <div class="text-sm text-gray-500">关注学者</div>
        </div>
        <div class="card p-6 text-center">
          <div class="text-2xl font-bold text-orange-600 dark:text-orange-400 mb-2">
            <span v-if="!loading">{{ stats.reading_history_count }}</span>
            <div v-else class="animate-pulse bg-gray-300 dark:bg-gray-600 h-8 w-8 mx-auto rounded"></div>
          </div>
          <div class="text-sm text-gray-500">阅读历史</div>
        </div>
      </div>

      <!-- 主要内容区域 -->
      <div class="grid lg:grid-cols-3 gap-8">
        <!-- 左侧：收藏和推荐 -->
        <div class="lg:col-span-2 space-y-8">
          <!-- 智能推荐 -->
          <div class="card p-6">
            <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">为您推荐</h2>
            
            <!-- 加载状态 -->
            <div v-if="loading" class="space-y-4">
              <div v-for="i in 3" :key="i" class="animate-pulse p-4 border border-gray-200 dark:border-gray-700 rounded">
                <div class="h-4 bg-gray-300 dark:bg-gray-600 rounded w-3/4 mb-2"></div>
                <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-2"></div>
                <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
              </div>
            </div>
            
            <!-- 实际内容 -->
            <div v-else-if="recommendations.length > 0" class="space-y-4">
              <div
                v-for="rec in recommendations"
                :key="rec.paper.id"
                class="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 p-4 rounded"
                @click="$router.push(`/papers/${rec.paper.short_id || rec.paper.id}`)"
              >
                <h3 class="font-medium text-gray-900 dark:text-white mb-1">{{ rec.paper.title }}</h3>
                <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">{{ rec.paper.author_names.join(', ') }}</p>
                <p class="text-xs text-blue-600 dark:text-blue-400">{{ rec.reason }}</p>
              </div>
            </div>
            
            <p v-else class="text-gray-500 dark:text-gray-400">暂无推荐内容</p>
          </div>

          <!-- 最近收藏 -->
          <div class="card p-6">
            <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">最近收藏</h2>
            
            <!-- 加载状态 -->
            <div v-if="loading" class="space-y-4">
              <div v-for="i in 3" :key="i" class="animate-pulse p-4">
                <div class="h-4 bg-gray-300 dark:bg-gray-600 rounded w-3/4 mb-2"></div>
                <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
              </div>
            </div>
            
            <!-- 实际内容 -->
            <div v-else-if="recentBookmarks.length > 0" class="space-y-4">
              <div
                v-for="paper in recentBookmarks"
                :key="paper.id"
                class="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 p-4 rounded"
                @click="$router.push(`/papers/${paper.short_id || paper.id}`)"
              >
                <h3 class="font-medium text-gray-900 dark:text-white mb-1">{{ paper.title }}</h3>
                <p class="text-sm text-gray-600 dark:text-gray-400">{{ paper.author_names.join(', ') }}</p>
              </div>
            </div>
            
            <p v-else class="text-gray-500 dark:text-gray-400">暂无收藏内容</p>
          </div>
        </div>

        <!-- 右侧：关注学者 -->
        <div class="space-y-8">
          <div class="card p-6">
            <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">关注学者</h2>
            
            <!-- 加载状态 -->
            <div v-if="loading" class="space-y-4">
              <div v-for="i in 3" :key="i" class="animate-pulse flex items-center space-x-3 p-3">
                <div class="w-10 h-10 bg-gray-300 dark:bg-gray-600 rounded-full"></div>
                <div class="flex-1">
                  <div class="h-3 bg-gray-300 dark:bg-gray-600 rounded w-3/4 mb-2"></div>
                  <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                </div>
              </div>
            </div>
            
            <!-- 实际内容 -->
            <div v-else-if="followedAuthors.length > 0" class="space-y-4">
              <div
                v-for="author in followedAuthors"
                :key="author.id"
                class="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 p-3 rounded"
                @click="$router.push(`/authors/${author.id}`)"
              >
                <div class="flex items-center space-x-3">
                  <div class="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center shrink-0">
                    <span class="text-white font-bold text-sm">
                      {{ getInitials(author.name) }}
                    </span>
                  </div>
                  <div>
                    <h3 class="font-medium text-gray-900 dark:text-white text-sm">{{ author.name }}</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">{{ author.affiliation }}</p>
                  </div>
                </div>
              </div>
            </div>
            
            <p v-else class="text-gray-500 dark:text-gray-400">暂无关注学者</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Paper, Author, Recommendation } from '@/types'
import { api } from '@/services/api'

const loading = ref(true)
const stats = ref({
  total_bookmarks: 0,
  total_folders: 0,
  followed_authors_count: 0,
  reading_history_count: 0
})

const recommendations = ref<Recommendation[]>([])
const recentBookmarks = ref<Paper[]>([])
const followedAuthors = ref<Author[]>([])

const getInitials = (name: string) => {
  return name
    .split(' ')
    .map(word => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const fetchDashboard = async () => {
  try {
    loading.value = true
    console.log('[DEBUG] 开始获取工作台数据')
    
    const [dashboardRes, recommendationsRes] = await Promise.all([
      api.workspace.dashboard(),
      api.workspace.recommendations({ limit: 5 })
    ])
    
    console.log('[DEBUG] 工作台API响应:', dashboardRes.data)
    console.log('[DEBUG] 推荐API响应:', recommendationsRes.data)
    
    const dashboard = dashboardRes.data
    console.log('[DEBUG] 解析后的工作台数据:', dashboard)
    
    stats.value = dashboard.user_stats
    console.log('[DEBUG] 设置统计信息:', stats.value)
    
    recentBookmarks.value = dashboard.recent_bookmarks
    console.log('[DEBUG] 设置最近收藏:', recentBookmarks.value)
    
    followedAuthors.value = dashboard.followed_authors
    console.log('[DEBUG] 设置关注作者:', followedAuthors.value)
    
    recommendations.value = recommendationsRes.data.recommendations
    console.log('[DEBUG] 设置推荐列表:', recommendations.value)
    
    console.log('[DEBUG] 最终状态值:')
    console.log('  - stats:', stats.value)
    console.log('  - recentBookmarks:', recentBookmarks.value)
    console.log('  - followedAuthors:', followedAuthors.value)
    console.log('  - recommendations:', recommendations.value)
  } catch (error: any) {
    console.error('[DEBUG] 获取工作台数据失败:', error)
    console.error('[DEBUG] 错误详情:', error.response?.data)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboard()
})
</script>

