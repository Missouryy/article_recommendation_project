<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 animate-fade-in">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- 搜索头部 -->
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-4">智能论文搜索</h1>
        <div class="max-w-3xl mx-auto">
          <div class="relative animate-scale-in">
            <input
              v-model="searchQuery"
              @keyup.enter="handleSearch"
              type="text"
              placeholder="搜索论文、作者或关键词..."
              class="w-full px-6 py-4 pr-16 text-lg rounded-full border border-gray-300 dark:border-gray-600 bg-white/95 dark:bg-gray-700/90 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-accent-500"
            >
            <button
              @click="handleSearch"
              :disabled="loading"
              class="absolute right-2 top-2 btn-primary rounded-full px-6 py-2 disabled:opacity-50"
            >
              {{ loading ? '搜索中...' : '搜索' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 搜索结果 -->
      <div v-if="searchResults.length > 0" class="space-y-6">
        <div class="text-sm text-gray-600 dark:text-gray-400">
          找到 {{ totalResults }} 篇相关论文
        </div>
        
        <!-- 视图切换标签 -->
        <div class="border-b border-gray-200 dark:border-gray-700">
          <nav class="-mb-px flex space-x-8">
            <button
              @click="activeView = 'list'"
              :class="[
                'py-2 px-1 border-b-2 font-medium text-sm transition-colors',
                activeView === 'list'
                  ? 'border-accent-500 text-accent-600 dark:text-accent-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
              ]"
            >
              列表视图
            </button>
            <button
              @click="activeView = 'graph'"
              :class="[
                'py-2 px-1 border-b-2 font-medium text-sm transition-colors',
                activeView === 'graph'
                  ? 'border-accent-500 text-accent-600 dark:text-accent-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
              ]"
            >
              引用图谱
            </button>
          </nav>
        </div>
        
        <!-- 列表视图 -->
        <div v-if="activeView === 'list'" class="grid gap-6">
          <div
            v-for="paper in searchResults"
            :key="paper.id"
            class="card-hover p-6 cursor-pointer"
            @click="selectPaper(paper)"
          >
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              {{ paper.title }}
            </h3>
            <p class="text-gray-600 dark:text-gray-400 text-sm mb-3">
              {{ paper.author_names.join(', ') }}
            </p>
            <div class="flex items-center justify-between text-sm text-gray-500">
              <span>{{ paper.year }} • {{ paper.journal }}</span>
              <span>{{ paper.citation_count }} 引用</span>
            </div>
          </div>
        </div>
        
        <!-- 引用图谱视图 -->
        <div v-if="activeView === 'graph'" class="space-y-4">
          <div v-if="selectedPaperForGraph" class="mb-4">
            <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <h3 class="text-lg font-semibold text-blue-900 dark:text-blue-100 mb-2">
                当前显示论文的引用关系图谱
              </h3>
              <p class="text-blue-800 dark:text-blue-200 text-sm">
                {{ selectedPaperForGraph.title }}
              </p>
              <p class="text-blue-700 dark:text-blue-300 text-xs mt-1">
                {{ selectedPaperForGraph.author_names.join(', ') }} • {{ selectedPaperForGraph.year }}
              </p>
            </div>
          </div>
          
          <div v-if="!selectedPaperForGraph" class="text-center py-12">
            <div class="text-gray-500 dark:text-gray-400 mb-4">
              <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
              </svg>
            </div>
            <p class="text-gray-500 dark:text-gray-400 mb-4">请从左侧列表中选择一篇论文来查看其引用关系图谱</p>
            <div class="text-sm text-gray-400 dark:text-gray-500">
              <p>图谱将显示：</p>
              <ul class="mt-2 space-y-1">
                <li>• 该论文引用的其他论文</li>
                <li>• 引用该论文的其他论文</li>
                <li>• 二级引用关系</li>
              </ul>
            </div>
          </div>
          
          <CitationGraph 
            v-if="selectedPaperForGraph" 
            :paper-id="selectedPaperForGraph.id"
            class="w-full"
          />
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading && searchQuery" class="text-center py-12">
        <p class="text-gray-500 dark:text-gray-400">未找到相关论文，请尝试其他关键词</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/services/api'
import CitationGraph from '@/components/CitationGraph.vue'

const route = useRoute()

const searchQuery = ref('')
const searchResults = ref([])
const totalResults = ref(0)
const loading = ref(false)
const activeView = ref('list')
const selectedPaperForGraph = ref(null)

const handleSearch = async () => {
  if (!searchQuery.value.trim()) return
  
  try {
    loading.value = true
    const response = await api.search.papers({
      query: searchQuery.value,
      search_type: 'hybrid',
      limit: 20
    })
    
    searchResults.value = response.data.papers
    totalResults.value = response.data.total
    
    // 如果有搜索结果，默认选择第一篇论文用于图谱显示
    if (response.data.papers.length > 0) {
      selectedPaperForGraph.value = response.data.papers[0]
    }
  } catch (error) {
    console.error('搜索失败:', error)
  } finally {
    loading.value = false
  }
}

const selectPaper = (paper: any) => {
  if (activeView.value === 'list') {
    // 在列表视图中点击论文，跳转到详情页
    window.open(`/papers/${paper.short_id || paper.id}`, '_blank')
  } else {
    // 在图谱视图中点击论文，更新图谱
    selectedPaperForGraph.value = paper
  }
}

onMounted(() => {
  const q = route.query.q as string
  if (q) {
    searchQuery.value = q
    handleSearch()
  }
})
</script>

