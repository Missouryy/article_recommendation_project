<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-col justify-center items-center min-h-[60vh]">
      <!-- 搜索头部 -->
  <div :class="!searched ? 'w-full flex flex-col items-center justify-center flex-1 min-h-[60vh]' : 'w-full flex flex-col items-center justify-center'">
        <h1
          v-if="!searched"
          class="text-6xl font-extrabold text-gray-900 dark:text-white mb-16 tracking-tight"
        >智能论文搜索</h1>
        <div v-if="!searched" class="w-full max-w-2xl">
          <div class="relative flex items-center w-full max-w-2xl">
            <input
              v-model="searchQuery"
              @keyup.enter="handleSearch"
              type="text"
              placeholder="搜索论文、作者或关键词..."
              class="input w-full px-7 py-5 pr-24 text-xl rounded-2xl bg-white dark:bg-gray-800 shadow-xl border border-blue-300 dark:border-blue-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-400 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 font-sans"
              style="font-family: -apple-system, BlinkMacSystemFont, 'San Francisco', 'Helvetica Neue', Arial, sans-serif;"
            >
            <button
              @click="handleSearch"
              :disabled="loading"
              class="absolute right-3 top-1/2 h-12 px-8 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-lg font-bold shadow-lg transition-colors flex items-center justify-center"
              style="font-family: inherit; transform: translateY(-50%);"
            >
              {{ loading ? '搜索中...' : '搜索' }}
            </button>
          </div>
        </div>
        <div v-else class="fixed bottom-8 left-0 right-0 z-30 flex justify-center">
          <div class="relative flex items-center w-full max-w-2xl">
            <input
              v-model="searchQuery"
              @keyup.enter="handleSearch"
              type="text"
              placeholder="搜索论文、作者或关键词..."
              class="input w-full px-7 py-5 pr-24 text-xl rounded-2xl bg-white/80 dark:bg-gray-800/80 shadow-xl border border-blue-300 dark:border-blue-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-400 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 font-sans"
              style="font-family: -apple-system, BlinkMacSystemFont, 'San Francisco', 'Helvetica Neue', Arial, sans-serif;"
            >
            <button
              @click="handleSearch"
              :disabled="loading"
              class="absolute right-3 top-1/2 h-12 px-8 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-lg font-bold shadow-lg transition-colors flex items-center justify-center"
              style="font-family: inherit; transform: translateY(-50%);"
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
        
        <!-- 结果列表 -->
        <div class="grid gap-6">
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
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="text-center py-12">
        <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 max-w-md mx-auto">
          <p class="text-red-600 dark:text-red-400 mb-4">{{ error }}</p>
          <button 
            @click="handleSearch"
            class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
          >
            重试搜索
          </button>
        </div>
      </div>
      
      <!-- 空状态 -->
      <div v-else-if="!loading && searchQuery && !error" class="text-center py-12">
        <p class="text-gray-500 dark:text-gray-400">未找到相关论文，请尝试其他关键词</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
// 简化本页列表项的显示类型，避免TS推断为never
type SearchItem = {
  id: string
  short_id?: string
  title: string
  author_names: string[]
  year: number
  journal: string
  citation_count: number
}
import { useRoute } from 'vue-router'
import { api } from '@/services/api'

const route = useRoute()

const searchQuery = ref('')
const searchResults = ref<SearchItem[]>([])
const totalResults = ref(0)
const loading = ref(false)
const error = ref('')
// 去掉图谱视图，默认只有列表
const activeView = ref('list')
const searched = ref(false)
const selectedPaperForGraph = ref(null)

const handleSearch = async () => {
  if (!searchQuery.value.trim()) return
  searched.value = true
  
  try {
    loading.value = true
    error.value = ''
    console.log('[SearchUI] 开始搜索:', searchQuery.value)
    
    const response = await api.search.papers({
      query: searchQuery.value,
      search_type: 'vector',
      limit: 20
    })
    
    console.log('[SearchUI] 搜索响应:', response.data)
    
    const papers = Array.isArray(response.data?.papers) ? response.data.papers : []
    const total = typeof response.data?.total === 'number' ? response.data.total : papers.length
    
    // 创建新引用触发渲染，并只保留必要字段避免响应式卡顿
    searchResults.value = papers.map((p: any) => ({
      id: p.id || p.paper_id,
      short_id: p.short_id || '',
      title: p.title || '',
      author_names: Array.isArray(p.author_names) ? p.author_names : [],
      year: p.year || 0,
      journal: p.journal || '',
      citation_count: p.citation_count || 0
    }))
    totalResults.value = total
    
    console.log('[SearchUI] 搜索结果处理完成:', {
      papersCount: papers.length,
      total: total,
      searchResultsLength: searchResults.value.length
    })
    
    // 不再在搜索时自动加载图谱
  } catch (err: any) {
    console.error('搜索失败:', err)
    // 显示错误信息给用户
    searchResults.value = []
    totalResults.value = 0
    
    // 设置错误信息
    if (err.response?.status === 500) {
      error.value = '系统正在加载中，请稍后重试'
    } else if (err.message?.includes('timeout')) {
      error.value = '搜索超时，请稍后重试'
    } else {
      error.value = '搜索失败，请稍后重试'
    }
    
    console.log('[SearchUI] 错误信息:', error.value)
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
    searched.value = true
    handleSearch()
  }
})
</script>


<style scoped>
.search-title-fade-enter-active, .search-title-fade-leave-active {
  transition: opacity 0.5s cubic-bezier(.4,0,.2,1);
}
.search-title-fade-enter-from, .search-title-fade-leave-to {
  opacity: 0;
}
.search-title-fade-enter-to, .search-title-fade-leave-from {
  opacity: 1;
}

.search-bar-move-enter-active, .search-bar-move-leave-active {
  transition: all 0.5s cubic-bezier(.4,0,.2,1);
}
.search-bar-move-enter-from, .search-bar-move-leave-to {
  opacity: 0;
  transform: translateY(40px);
}
.search-bar-move-enter-to, .search-bar-move-leave-from {
  opacity: 1;
  transform: translateY(0);
}
.search-header-move-enter-active, .search-header-move-leave-active {
  transition: all 0.5s cubic-bezier(.4,0,.2,1);
}
.search-header-move-enter-from, .search-header-move-leave-to {
  opacity: 0;
  transform: translateY(40px);
}
.search-header-move-enter-to, .search-header-move-leave-from {
  opacity: 1;
  transform: translateY(0);
}

.search-title-fade-enter-active, .search-title-fade-leave-active {
  transition: opacity 0.5s cubic-bezier(.4,0,.2,1);
}
.search-title-fade-enter-from, .search-title-fade-leave-to {
  opacity: 0;
}
.search-title-fade-enter-to, .search-title-fade-leave-from {
  opacity: 1;
}
.search-header-move-enter-active, .search-header-move-leave-active {
  transition: all 0.5s cubic-bezier(.4,0,.2,1);
}
.search-header-move-enter-from, .search-header-move-leave-to {
  opacity: 0;
  transform: translateY(40px);
}
.search-header-move-enter-to, .search-header-move-leave-from {
  opacity: 1;
  transform: translateY(0);
}
</style>

