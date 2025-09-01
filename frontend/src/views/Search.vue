<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 animate-fade-in">
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

      <!-- 搜索结果与空状态 -->
      <div>
        <template v-if="searchResults.length > 0">
          <div class="mt-0">
            <div class="mb-8">
              <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">搜索结果</h1>
              <p class="text-gray-600 dark:text-gray-300">找到 {{ totalResults }} 篇相关论文</p>
            </div>
            <div class="grid gap-6">
              <div
                v-for="paper in searchResults"
                :key="paper.id"
                class="card-hover p-6 cursor-pointer"
                @click="goToDetail(paper.short_id)"
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
import { ref, onMounted, onActivated } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/services/api'
import type { Paper } from '@/types'

const route = useRoute()
const router = useRouter()
const searchQuery = ref('')
const searchResults = ref<Paper[]>([])
const totalResults = ref(0)
const loading = ref(false)
const searched = ref(false)

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

const handleSearch = async () => {
  if (!searchQuery.value.trim()) return
  searched.value = true
  try {
    loading.value = true
    const response = await api.search.papers({
      query: searchQuery.value,
      search_type: 'hybrid',
      limit: 20
    })

    searchResults.value = response.data.papers
    totalResults.value = response.data.total
  } catch (error) {
    console.error('搜索失败:', error)
  } finally {
    loading.value = false
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
.search-bar-move-enter-active, .search-header-move-enter-active {
  transition: all 0.5s cubic-bezier(.4, 0, .2, 1);
}

.search-bar-move-enter-from, .search-header-move-enter-from {
  opacity: 0;
  transform: translateY(40px);
}

.search-bar-move-enter-to, .search-header-move-enter-to {
  opacity: 1;
  transform: translateY(0);
}

.search-title-fade-leave-active, .search-bar-move-leave-active, .search-header-move-leave-active {
  transition: all 0s;
}
</style>
