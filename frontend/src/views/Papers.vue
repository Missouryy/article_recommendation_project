<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">论文库</h1>
        <p class="text-gray-600 dark:text-gray-300">浏览和发现学术论文</p>
      </div>

      <!-- 论文列表 -->
      <div v-if="papers.length > 0" class="grid gap-6">
        <div
          v-for="paper in papers"
          :key="paper.id"
          class="card-hover p-6 cursor-pointer animate-slide-in"
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

      <!-- 加载状态 -->
      <div v-else-if="loading" class="text-center py-12">
        <div class="spinner mx-auto"></div>
        <p class="text-gray-500 dark:text-gray-400 mt-4">加载中...</p>
      </div>

      <!-- 分页控制 -->
      <div class="mt-10 flex items-center justify-center space-x-4">
        <button
          @click="prevPage"
          :disabled="page <= 1 || loading"
          class="h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-base font-bold shadow-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >上一页</button>
        <span class="text-gray-700 dark:text-gray-300">第 {{ page }} 页</span>
        <button
          @click="nextPage"
          :disabled="loading || papers.length < pageSize"
          class="h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-base font-bold shadow-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Papers' })
import { ref, onMounted, onActivated } from 'vue'
import type { Paper } from '@/types'
import { api } from '@/services/api'
import { useRouter } from 'vue-router'

const papers = ref<Paper[]>([])
const loading = ref(false)
const router = useRouter()

let lastScrollTop = 0
const page = ref(1)
const pageSize = ref(20)

const goToDetail = (short_id: string) => {
  lastScrollTop = window.scrollY
  router.push(`/papers/${short_id}`)
}

onActivated(() => {
  if (lastScrollTop) {
    window.scrollTo(0, lastScrollTop)
  }
})

const fetchPapers = async () => {
  try {
    loading.value = true
    const response = await api.papers.list({
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
      sort_by: 'date',
      order: 'desc'
    })
    papers.value = response.data
  } catch (error) {
    console.error('获取论文失败:', error)
  } finally {
    loading.value = false
  }
}

const nextPage = async () => {
  if (loading.value) return
  page.value += 1
  await fetchPapers()
  window.scrollTo(0, 0)
}

const prevPage = async () => {
  if (loading.value || page.value <= 1) return
  page.value -= 1
  await fetchPapers()
  window.scrollTo(0, 0)
}

onMounted(() => {
  fetchPapers()
})
</script>

