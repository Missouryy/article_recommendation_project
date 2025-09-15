<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 animate-fade-in">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-28 flex-col justify-center items-center min-h-[60vh]">
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
              @keyup.enter="handleSearch(true)"
              type="text"
              placeholder="搜索论文、作者或关键词..."
              class="input w-full px-7 py-5 pr-24 text-xl rounded-2xl bg-white/80 dark:bg-gray-800/80 shadow-xl border border-blue-300 dark:border-blue-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-400 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 font-sans"
              style="font-family: -apple-system, BlinkMacSystemFont, 'San Francisco', 'Helvetica Neue', Arial, sans-serif;"
            >
            <button
              @click="handleSearch(true)"
              :disabled="loading"
              class="absolute right-3 top-1/2 h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-lg font-bold shadow-lg transition-colors flex items-center justify-center w-24"
              style="font-family: inherit; transform: translateY(-50%);"
            >
              {{ loading ? '...' : '搜索' }}
            </button>
          </div>
        </div>
        <div v-else class="fixed bottom-8 left-0 right-0 z-30 flex justify-center">
          <div class="relative flex items-center w-full max-w-2xl">
            <input
              v-model="searchQuery"
              @keyup.enter="handleSearch(true)"
              type="text"
              placeholder="搜索论文、作者或关键词..."
              class="input w-full px-7 py-5 pr-24 text-xl rounded-2xl bg-white/80 dark:bg-gray-800/80 shadow-xl border border-blue-300 dark:border-blue-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-400 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 font-sans"
              style="font-family: -apple-system, BlinkMacSystemFont, 'San Francisco', 'Helvetica Neue', Arial, sans-serif;"
            >
            <button
              @click="handleSearch(true)"
              :disabled="loading"
              class="absolute right-3 top-1/2 h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-lg font-bold shadow-lg transition-colors flex items-center justify-center w-24"
              style="font-family: inherit; transform: translateY(-50%);"
            >
              {{ loading ? '...' : '搜索' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 搜索结果与空状态 -->
      <div>
        <template v-if="searchResults.length > 0">
          <div class="mt-0">
            <div class="mb-8">
              <div class="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-1">搜索结果</h1>
                  <p class="text-gray-600 dark:text-gray-300">找到 {{ totalResults }} 篇相关论文</p>
                </div>
                <div class="flex items-center space-x-3">
                  <select 
                      v-model="sortBy" 
                      @change="handleSearch(true)" 
                      class="pl-4 pr-9 py-2.5 rounded-xl bg-white dark:bg-gray-800 border border-blue-300 dark:border-blue-500 hover:border-blue-500 dark:hover:border-blue-400 text-gray-900 dark:text-white transition-colors"
                  >
                      <option value="relevance">相关度</option>
                      <option value="date">日期</option>
                      <option value="citation">引用数</option>
                      <option value="truth_value">真值</option>
                  </select>

                  <select 
                      v-model="sortOrder" 
                      @change="handleSearch(true)" 
                      class="pl-4 pr-9 py-2.5 rounded-xl bg-white dark:bg-gray-800 border border-blue-300 dark:border-blue-500 hover:border-blue-500 dark:hover:border-blue-400 text-gray-900 dark:text-white transition-colors"
                  >
                      <option value="desc">降序</option>
                      <option value="asc">升序</option>
                  </select>
                </div>
              </div>
            </div>
            <div class="grid gap-6">
              <div
                v-for="paper in searchResults"
                :key="paper.id"
                class="card-hover p-6 cursor-pointer"
                @click="goToDetail(paper.short_id || paper.id)"
              >
                <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  {{ paper.title }}
                </h3>
                <p class="text-gray-600 dark:text-gray-400 text-sm mb-3">
                  {{ paper.author_names.join(', ') }}
                </p>
                <div class="flex items-center justify-between text-sm">
                  <span class="text-gray-500">{{ paper.year }} • {{ paper.journal }}</span>
                  <div class="flex items-center space-x-4">
                    <span class="text-blue-600 dark:text-blue-400">{{ paper.citation_count }} 引用</span>
                    <span v-if="paper.truth_value_score" class="badge-primary">
                      真值: {{ paper.truth_value_score.toFixed(1) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="totalPages > 1" class="mt-10 flex items-center justify-center space-x-4">
              <button
                @click="prevPage"
                :disabled="currentPage <= 1 || loading"
                class="h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-base font-bold shadow-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >上一页</button>
              <span class="text-gray-700 dark:text-gray-300">第 {{ currentPage }} / {{ totalPages }} 页</span>
              <button
                @click="nextPage"
                :disabled="currentPage >= totalPages || loading"
                class="h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-base font-bold shadow-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >下一页</button>
            </div>
          </div>
        </template>
        <template v-else-if="error">
          <div class="text-center py-12">
            <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 max-w-md mx-auto">
              <p class="text-red-600 dark:text-red-400 mb-4">{{ error }}</p>
              <button 
                @click="handleSearch()"
                class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                重试搜索
              </button>
            </div>
          </div>
        </template>
        <template v-else-if="searched && !loading && searchResults.length === 0">
          <div class="text-center py-16">
            <p class="text-gray-500 dark:text-gray-400 text-xl font-medium">未找到相关论文，请尝试其他关键词</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Search' })
import { ref, onMounted, onActivated, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/services/api'
type SearchItem = {
  id: string
  short_id?: string
  title: string
  author_names: string[]
  year: number
  journal: string
  citation_count: number
  truth_value_score?: number
}

const route = useRoute()
const router = useRouter()
const searchQuery = ref('')
const searchResults = ref<SearchItem[]>([])
const totalResults = ref(0)
const loading = ref(false)
const error = ref('')
const searched = ref(false)
const pageSize = ref(20)
const currentPage = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(totalResults.value / pageSize.value)))
const sortBy = ref<'relevance' | 'date' | 'citation' | 'truth_value'>('relevance')
const sortOrder = ref<'asc' | 'desc'>('desc')

let lastScrollTop = 0

const goToDetail = (short_id: string) => {
  lastScrollTop = window.scrollY
  router.push(`/papers/${short_id}`)
}

onActivated(() => {
  if (lastScrollTop) {
    window.scrollTo(0, lastScrollTop)
  }
})

const updateRouteQuery = () => {
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      q: searchQuery.value,
      page: String(currentPage.value),
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    },
  })
}

const handleSearch = async (resetPage = false) => {
  if (!searchQuery.value.trim()) return
  if (resetPage) currentPage.value = 1
  searched.value = true
  try {
    loading.value = true
    error.value = ''
    const response = await api.search.papers({
      query: searchQuery.value,
      search_type: 'vector',
      limit: 20
    })
    const papers = Array.isArray(response.data?.papers) ? response.data.papers : []
    const total = typeof response.data?.total === 'number' ? response.data.total : papers.length
    searchResults.value = papers.map((p: any) => ({
      id: p.id || p.paper_id,
      short_id: p.short_id || '',
      title: p.title || '',
      author_names: Array.isArray(p.author_names) ? p.author_names : [],
      year: p.year || 0,
      journal: p.journal || '',
      citation_count: p.citation_count || 0,
      truth_value_score: p.truth_value_score
    }))
    totalResults.value = total
    updateRouteQuery()
  } catch (err: any) {
    console.error('搜索失败:', err)
    searchResults.value = []
    totalResults.value = 0
    if (err.response?.status === 500) {
      error.value = '系统正在加载中，请稍后重试'
    } else if (err.message?.includes('timeout')) {
      error.value = '搜索超时，请稍后重试'
    } else {
      error.value = '搜索失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}

const nextPage = async () => {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
  await handleSearch(false)
}

const prevPage = async () => {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  await handleSearch(false)
}

onMounted(() => {
  const q = route.query.q as string
  const pageParam = Number(route.query.page || 1)
  const sortByParam = (route.query.sort_by as string) || 'relevance'
  const sortOrderParam = (route.query.sort_order as string) || 'desc'
  if (q) {
    searchQuery.value = q
    currentPage.value = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1
    if (['relevance', 'date', 'citation', 'truth_value'].includes(sortByParam)) {
      sortBy.value = sortByParam as any
    }
    if (['asc', 'desc'].includes(sortOrderParam)) {
      sortOrder.value = sortOrderParam as any
    }
    searched.value = true
    handleSearch(false)
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
</style>
