<template>
  <div class="min-h-screen">
    <!-- Hero Section -->
  <section class="relative bg-blue-600 text-white">
      <div class="absolute inset-0 bg-black opacity-20"></div>
      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
        <div class="text-center">
          <h1 class="text-4xl md:text-6xl font-bold mb-6 animate-fade-in">
            学术论文推荐系统
          </h1>
          <p class="text-xl md:text-2xl mb-8 text-blue-100 animate-slide-in">
            智能搜索 · 深度分析 · 个性推荐
          </p>
          
          <!-- 搜索框 -->
          <div class="max-w-2xl mx-auto mb-8">
            <div class="relative">
              <input
                v-model="searchQuery"
                @keyup.enter="handleSearch"
                type="text"
                placeholder="搜索论文、作者或关键词..."
                class="input w-full px-7 py-5 pr-24 text-xl rounded-2xl bg-white/80 dark:bg-gray-800/80 shadow-xl border border-blue-300 dark:border-blue-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-400 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 font-sans backdrop-blur"
                style="font-family: -apple-system, BlinkMacSystemFont, 'San Francisco', 'Helvetica Neue', Arial, sans-serif;"
              >
              <button
                @click="handleSearch"
                class="absolute right-3 top-1/2 h-12 px-7 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-md transition-colors flex items-center justify-center"
                style="font-family: inherit; transform: translateY(-50%);"
              >
                搜索
              </button>
            </div>
          </div>
          
          <!-- 快速操作 -->
          <div class="flex flex-wrap justify-center gap-4">
            <router-link to="/papers" class="btn-secondary bg-white/20 hover:bg-white/30 backdrop-blur text-gray-100">
              浏览论文库
            </router-link>
            <router-link to="/authors" class="btn-secondary bg-white/20 hover:bg-white/30 backdrop-blur text-gray-100">
              学者画像
            </router-link>
            <router-link v-if="!userStore.isAuthenticated" to="/register" class="btn-primary">
              免费注册
            </router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- 特色功能 -->
  <section class="py-20 bg-white dark:bg-gray-900">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-16">
          <h2 class="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            强大功能，助力学术研究
          </h2>
          <p class="text-xl text-gray-600 dark:text-gray-300">
            集成多种先进技术，为学者提供全方位的研究支持
          </p>
        </div>
        
        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div v-for="feature in features" :key="feature.title" class="card-hover p-6 text-center">
            <div class="w-16 h-16 mx-auto mb-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
              <component :is="feature.icon" class="w-8 h-8 text-white" />
            </div>
            <h3 class="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              {{ feature.title }}
            </h3>
            <p class="text-gray-600 dark:text-gray-300">
              {{ feature.description }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 统计数据 -->
  <section class="py-16 bg-gray-50 dark:bg-gray-800">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div v-for="stat in stats" :key="stat.label" class="animate-fade-in">
            <div class="text-3xl md:text-4xl font-bold text-blue-600 dark:text-blue-400 mb-2">
              {{ stat.value }}
            </div>
            <div class="text-gray-600 dark:text-gray-300">
              {{ stat.label }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 热门论文 -->
  <section v-if="trendingPapers.length > 0" class="py-20 bg-white dark:bg-gray-900">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-4">
            热门论文
          </h2>
          <p class="text-gray-600 dark:text-gray-300">
            发现最新的学术动态和研究热点
          </p>
        </div>
        
        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="paper in trendingPapers"
            :key="paper.id"
            class="card-hover p-6 cursor-pointer"
            @click="$router.push(`/papers/${paper.short_id || paper.id}`)"
          >
            <h3 class="font-semibold text-gray-900 dark:text-white mb-2 line-clamp-2">
              {{ paper.title }}
            </h3>
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
              {{ paper.author_names.join(', ') }}
            </p>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500">{{ paper.year }}</span>
              <span class="text-blue-600 dark:text-blue-400">
                {{ paper.citation_count }} 引用
              </span>
            </div>
          </div>
        </div>
        
        <div class="text-center mt-8 max-w-sm mx-auto">
          <router-link to="/papers" class="btn btn-lg bg-white text-blue-600 shadow-md hover:bg-gray-100 dark:bg-gray-800 dark:text-blue-400 dark:hover:bg-gray-700">
            查看更多论文
          </router-link>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
  <section class="py-20 bg-blue-600 text-white">
      <div class="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
        <h2 class="text-3xl md:text-4xl font-bold mb-4">
          开始您的学术探索之旅
        </h2>
        <p class="text-xl mb-8 text-blue-100">
          加入我们，体验前所未有的学术研究体验
        </p>
        <div class="flex flex-col sm:flex-row gap-4 justify-center">
          <router-link v-if="!userStore.isAuthenticated" to="/register" class="btn bg-white text-blue-600 hover:bg-gray-100">
            立即注册
          </router-link>
          <router-link v-else to="/workspace" class="btn bg-white text-blue-600 hover:bg-gray-100 dark:bg-gray-800 dark:text-blue-400 dark:hover:bg-gray-700">
            进入工作台
          </router-link>
          <router-link to="/search" class="btn border-2 border-white text-white hover:bg-white hover:text-blue-600 dark:hover:bg-gray-800 dark:hover:text-blue-400">
            开始搜索
          </router-link>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Paper } from '@/types'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { api } from '@/services/api'

// Icons (简化处理，实际项目中可以使用图标库)
const SearchIcon = 'div'
const ChartBarIcon = 'div'
const UserGroupIcon = 'div'
const AcademicCapIcon = 'div'
const SparklesIcon = 'div'
const CpuChipIcon = 'div'

const router = useRouter()
const userStore = useUserStore()

const searchQuery = ref('')

const trendingPapers = ref<Paper[]>([])
const loading = ref(false)

const features = ref([
  {
    title: '智能搜索',
    description: '混合搜索、语义搜索，精准找到所需论文',
    icon: SearchIcon
  },
  {
    title: '深度分析',
    description: '真值算法评估，多维度论文质量分析',
    icon: ChartBarIcon
  },
  {
    title: '作者画像',
    description: '学术轨迹分析，合作网络可视化',
    icon: UserGroupIcon
  },
  {
    title: '知识图谱',
    description: '引用关系网络，学术脉络一目了然',
    icon: AcademicCapIcon
  },
  {
    title: 'AI助手',
    description: '论文总结、对比分析、研究建议',
    icon: SparklesIcon
  },
  {
    title: '个性推荐',
    description: '基于兴趣和行为的智能推荐系统',
    icon: CpuChipIcon
  }
])

const stats = ref([
  { value: '10K+', label: '论文数量' },
  { value: '2K+', label: '活跃学者' },
  { value: '500+', label: '研究机构' },
  { value: '50+', label: '研究领域' }
])

const handleSearch = () => {
  if (searchQuery.value.trim()) {
    router.push({
      path: '/search',
      query: { q: searchQuery.value.trim() }
    })
  }
}

const fetchTrendingPapers = async () => {
  try {
    loading.value = true
    const response = await api.papers.list({
      limit: 6,
      sort_by: 'citation',
      order: 'desc'
    })
    trendingPapers.value = response.data
  } catch (error) {
    console.error('获取热门论文失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTrendingPapers()
})
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

