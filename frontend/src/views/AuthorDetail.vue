<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <div v-if="author" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- 返回按钮（卡片外） -->
      <button @click="goBack" class="mb-6 btn-secondary flex items-center gap-2 hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
        返回
      </button>

      <!-- 作者信息 -->
      <div class="card p-8 mb-8">
        <div class="flex items-start space-x-6">
          <div class="w-24 h-24 bg-blue-600 rounded-full flex items-center justify-center">
            <span class="text-white font-bold text-2xl">
              {{ getInitials(author?.name || '') }}
            </span>
          </div>
          
          <div class="flex-1">
            <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              {{ author?.name }}
            </h1>
            
            <p class="text-lg text-gray-600 dark:text-gray-400 mb-4">
              {{ author?.affiliation }}
            </p>
            
            <div class="grid grid-cols-2 gap-6 mb-6">
              <div class="text-center">
                <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">{{ author?.citation_count }}</div>
                <div class="text-sm text-gray-500">引用数</div>
              </div>
              <div class="text-center">
                <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">{{ author?.paper_count }}</div>
                <div class="text-sm text-gray-500">论文数</div>
              </div>
            </div>
            
            <div class="mb-6">
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">研究领域</h3>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="area in (author?.research_areas || [])"
                  :key="area"
                  class="badge-primary"
                >
                  {{ area }}
                </span>
              </div>
            </div>
            
              <div v-if="author?.bio" class="mb-6">
              <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">简介</h3>
                <p class="text-gray-700 dark:text-gray-300">{{ author?.bio }}</p>
            </div>
            
            <!-- 操作按钮 -->
            <div class="flex gap-4">
              <button
                @click="toggleFollow"
                :class="[
                  'btn',
                  isFollowing ? 'btn-danger' : 'btn-primary'
                ]"
              >
                {{ isFollowing ? '取消关注' : '关注学者' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 代表作品 -->
      <div class="card p-6 mb-8">
        <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">代表作品</h2>
        <div v-if="papersLoading" class="text-center py-8">
          <div class="spinner mx-auto"></div>
          <p class="text-gray-500 dark:text-gray-400 mt-3">加载论文列表...</p>
        </div>
        <div v-else-if="papers.length > 0" class="space-y-4">
          <div
            v-for="paper in papers"
            :key="paper.id"
            class="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 p-4 rounded"
            @click="$router.push(`/papers/${paper.short_id || paper.id}`)"
          >
            <h3 class="font-medium text-gray-900 dark:text-white mb-1">{{ paper.title }}</h3>
            <div class="flex items-center justify-between text-sm text-gray-500">
              <span>{{ paper.year }} • {{ paper.journal }}</span>
              <span>{{ paper.citation_count }} 引用</span>
            </div>
          </div>
        </div>
        <p v-else class="text-gray-500 dark:text-gray-400">暂无论文数据</p>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-else-if="loading" class="min-h-screen flex items-center justify-center">
      <div class="text-center">
        <div class="spinner mx-auto mb-4"></div>
        <p class="text-gray-500 dark:text-gray-400">加载学者信息...</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/services/api'
import { useUserStore } from '@/stores/user'
import type { Author, Paper } from '@/types'

const route = useRoute()
const userStore = useUserStore()

const author = ref<Author | null>(null)
const papers = ref<Paper[]>([])
const papersLoading = ref(false)
const loading = ref(false)
const isFollowing = ref(false)

const getInitials = (name: string) => {
  return name
    .split(' ')
    .map(word => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const fetchAuthor = async () => {
  try {
    loading.value = true
    const authorId = route.params.id as string

    // 先拿作者信息，先展示主体信息
    const authorRes = await api.authors.get(authorId)
    author.value = authorRes.data

    // 并行或延后获取论文列表，单独 loading
    papersLoading.value = true
    api.authors.papers(authorId, { limit: 10, sort_by: 'citation', order: 'desc' })
      .then(res => { papers.value = res.data })
      .catch(() => { papers.value = [] })
      .finally(() => { papersLoading.value = false })

    // 判断当前用户是否已关注该学者
    if (userStore.isAuthenticated) {
      try {
        const followedRes = await api.workspace.followedAuthors()
        const followedList = followedRes.data as Author[]
        // 将ID转换为姓名进行匹配
        const authorName = authorId.replace(/_/g, ' ')
        isFollowing.value = followedList.some(a => a.name === authorName)
      } catch (e) {
        // 忽略关注列表获取失败
        isFollowing.value = false
      }
    } else {
      isFollowing.value = false
    }

  } catch (error) {
    console.error('获取学者信息失败:', error)
  } finally {
    loading.value = false
  }
}

const toggleFollow = async () => {
  if (!userStore.isAuthenticated) {
    return
  }
  
  try {
    const authorId = decodeURIComponent(route.params.id as string)
    // 将ID转换为作者姓名（将下划线替换为空格）
    const authorName = authorId.replace(/_/g, ' ')
    
    if (isFollowing.value) {
      await api.authors.unfollow(authorName)
      isFollowing.value = false
    } else {
      await api.authors.follow(authorName)
      isFollowing.value = true
    }
  } catch (error) {
    console.error('关注操作失败:', error)
  }
}

const goBack = () => {
  if (window.history.length > 1) {
    window.history.back()
  } else {
    // 无历史记录则回到学者库
    window.location.href = '/authors'
  }
}

onMounted(() => {
  fetchAuthor()
})
</script>

