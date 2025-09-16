<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">学者库</h1>
        <p class="text-gray-600 dark:text-gray-300">探索学术界的杰出学者</p>
      </div>

      <!-- 学者列表 -->
      <div v-if="authors.length > 0" class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="author in authors"
          :key="author.id"
          class="card-hover p-6 cursor-pointer"
          @click="goToAuthor(author.id)"
        >
          <div class="text-center">
            <div class="w-16 h-16 mx-auto mb-4 bg-blue-600 rounded-full flex items-center justify-center">
              <span class="text-white font-bold text-lg">
                {{ getInitials(author.name) }}
              </span>
            </div>
            
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              {{ author.name }}
            </h3>
            
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
              {{ author.affiliation }}
            </p>
            
            <div class="mt-3 flex flex-wrap justify-center gap-1">
              <span
                v-for="area in (author.research_areas ? author.research_areas.slice(0, 3) : [])"
                :key="area"
                class="badge-secondary text-xs"
              >
                {{ area }}
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
          :disabled="loading || authors.length < pageSize"
          class="h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-base font-bold shadow-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/services/api'
import type { Author } from '@/types'

const authors = ref<Author[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(30)
const router = useRouter()

const getInitials = (name: string) => {
  return name
    .split(' ')
    .map(word => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const fetchAuthors = async () => {
  try {
    loading.value = true
    const response = await api.authors.list({
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value
    })
    authors.value = response.data
  } catch (error) {
    console.error('获取学者失败:', error)
  } finally {
    loading.value = false
  }
}

const goToAuthor = (id: string) => {
  try {
    sessionStorage.setItem('authors_restore', '1')
    sessionStorage.setItem('authors_scroll', String(window.scrollY || 0))
  } catch (e) {}
  router.push(`/authors/${encodeURIComponent(id)}`)
}

const nextPage = async () => {
  if (loading.value) return
  page.value += 1
  await fetchAuthors()
  window.scrollTo(0, 0)
}

const prevPage = async () => {
  if (loading.value || page.value <= 1) return
  page.value -= 1
  await fetchAuthors()
  window.scrollTo(0, 0)
}

onMounted(() => {
  // 重新打开学者库时不恢复滚动位置，清理可能的遗留状态
  try {
    sessionStorage.removeItem('authors_restore')
    sessionStorage.removeItem('authors_scroll')
  } catch (e) {}
  fetchAuthors()
})

onActivated(() => {
  // 仅当从作者详情返回时恢复滚动
  try {
    const shouldRestore = sessionStorage.getItem('authors_restore') === '1'
    if (shouldRestore) {
      const y = Number(sessionStorage.getItem('authors_scroll') || '0')
      if (!Number.isNaN(y) && y > 0) {
        window.scrollTo(0, y)
      }
      sessionStorage.removeItem('authors_restore')
      sessionStorage.removeItem('authors_scroll')
    } else {
      // 非返回场景（重新进入学者库），重置到第一页并回到顶部
      page.value = 1
      fetchAuthors()
      window.scrollTo(0, 0)
    }
  } catch (e) {}
})
</script>

