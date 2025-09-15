<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- 页面标题区域 -->
    <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-gray-900 dark:text-white flex items-center">
              <svg class="w-8 h-8 mr-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              智能推荐
            </h1>
            <p class="mt-2 text-gray-600 dark:text-gray-300">
              基于BERT向量语义分析，为您提供精准的论文推荐服务
            </p>
            <div class="mt-3 text-sm text-gray-500 dark:text-gray-400 space-y-1">
              <p><strong class="text-blue-600">日常推荐：</strong>基于前5篇收藏论文（权重1）+ 前10篇阅读历史（权重1.5）</p>
              <p><strong class="text-green-600">喜好推荐：</strong>基于10篇收藏论文（权重2）+ 前10篇阅读历史（权重1）</p>
              <p><strong class="text-purple-600">热门推荐：</strong>基于论文引用数和发表时间的热门论文</p>
              <p><strong class="text-red-500">真值推荐：</strong>基于论文计算得出的真值</p>
            </div>
          </div>
          <div class="flex space-x-3">
            <button 
              @click="refreshRecommendations"
              :disabled="loading"
              class="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg class="w-4 h-4 mr-2" :class="{ 'animate-spin': loading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              刷新推荐
            </button>
            <button 
              @click="showStats = true"
              class="btn-primary"
            >
              <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              推荐统计
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- 推荐类型切换 -->
      <div class="mb-8">
        <nav class="flex space-x-8" aria-label="推荐类型">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            @click="activeTab = tab.key; loadRecommendations()"
            :class="[
              activeTab === tab.key
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200',
              'whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm'
            ]"
          >
            {{ tab.name }}
          </button>
        </nav>
      </div>

      <!-- 热门主题标签 -->
      <div v-if="(activeTab === 'daily' || activeTab === 'preference') && trendingTopics.length > 0" class="mb-8">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">热门研究主题</h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="topic in trendingTopics.slice(0, 8)"
            :key="topic.topic"
            class="badge-primary"
          >
            {{ topic.topic }}
            <span class="ml-1">({{ topic.paper_count }})</span>
          </span>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="flex justify-center items-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <span class="ml-3 text-gray-600 dark:text-gray-300">正在生成智能推荐...</span>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-md p-4 mb-6">
        <div class="flex">
          <svg class="h-5 w-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-red-800 dark:text-red-200">推荐加载失败</h3>
            <p class="mt-1 text-sm text-red-700 dark:text-red-300">{{ error }}</p>
            <button 
              @click="loadRecommendations"
              class="mt-2 text-sm font-medium text-red-600 dark:text-red-400 hover:text-red-500"
            >
              重试
            </button>
          </div>
        </div>
      </div>

      <!-- 推荐结果 -->
      <div v-else-if="recommendations.length > 0">
        <!-- 推荐摘要信息 -->
        <div
            v-if="activeTab !== 'truth'"
            class="bg-blue-50 dark:bg-blue-900 border border-blue-200 dark:border-blue-700 rounded-lg p-4 mb-6"
        >
          <div class="flex items-center">
            <svg class="h-5 w-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="ml-2 text-sm text-blue-700 dark:text-blue-200">
              为您找到 <strong>{{ recommendations.length }}</strong> 篇推荐论文，
              平均相关性评分 <strong>{{ averageRelevanceScore.toFixed(2) }}</strong>
            </p>
          </div>
        </div>

        <!-- 论文列表 -->
        <div class="space-y-6">
          <div
            v-for="(paper, index) in recommendations"
            :key="paper.paper_id"
            class="card card-hover animate-slide-in"
          >
            <div class="p-6">
              <!-- 论文标题和基本信息 -->
              <div class="flex items-start justify-between">
                <div class="flex-1">
                  <div class="flex items-center mb-2">
                    <span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 text-sm font-medium mr-3">
                      {{ index + 1 }}
                    </span>
                    <h3 class="text-lg font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer"
                        @click="viewPaper(paper)">
                      {{ paper.title }}
                    </h3>
                  </div>
                  
                  <!-- 论文元信息 -->
                  <div class="flex flex-wrap items-center text-sm text-gray-500 dark:text-gray-400 mb-3 space-x-4">
                    <span v-if="paper.year" class="flex items-center">
                      <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      {{ paper.year }}
                    </span>
                    <span v-if="paper.journal" class="flex items-center">
                      <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                      </svg>
                      {{ paper.journal }}
                    </span>
                    <span class="flex items-center">
                      <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                      </svg>
                      {{ paper.citation_count }} 次引用
                    </span>
                  </div>

                  <!-- 推荐理由 -->
                  <div class="mb-4">
                    <p class="text-sm text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 rounded-md px-3 py-2">
                      <span class="font-medium text-blue-600 dark:text-blue-400">推荐理由：</span>
                      {{ paper.recommendation_reason }}
                    </p>
                  </div>

                  <!-- 评分指标 -->
                  <div class="flex items-center space-x-6 mb-4">
                    <div class="flex items-center">
                      <span class="text-xs font-medium text-gray-500 dark:text-gray-400 mr-2">相关性</span>
                      <div class="flex items-center">
                        <div class="w-20 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                          <div 
                            class="bg-blue-600 h-2 rounded-full" 
                            :style="{ width: (paper.relevance_score * 100) + '%' }"
                          ></div>
                        </div>
                        <span class="ml-2 text-xs font-medium text-gray-700 dark:text-gray-300">
                          {{ (paper.relevance_score * 100).toFixed(0) }}%
                        </span>
                      </div>
                    </div>
                    <div class="flex items-center">
                      <span class="text-xs font-medium text-gray-500 dark:text-gray-400 mr-2">重要度</span>
                      <div class="flex items-center">
                        <div class="w-20 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                          <div 
                            class="bg-green-600 h-2 rounded-full" 
                            :style="{ width: (paper.importance_score * 100) + '%' }"
                          ></div>
                        </div>
                        <span class="ml-2 text-xs font-medium text-gray-700 dark:text-gray-300">
                          {{ (paper.importance_score * 100).toFixed(0) }}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <span
                  v-if="activeTab === 'truth' || paper.truth_value != null"
                  class="ml-4 px-2 py-1 rounded-md text-xs bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 whitespace-nowrap"
                >
                  真值：{{ paper.truth_value_text ?? ((paper.truth_value ?? 0) * 100).toFixed(1) + '分' }}
                </span>

                <!-- 操作按钮 -->
                <div class="flex flex-col space-y-2 ml-4">
                  <button
                    @click="viewPaper(paper)"
                    class="btn-secondary"
                  >
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    查看详情
                  </button>
                  <div class="flex space-x-1">
                    <button
                      @click="provideFeedback(paper.paper_id, 'like')"
                      class="inline-flex items-center p-2 text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-900 rounded-md"
                      title="喜欢这个推荐"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                      </svg>
                    </button>
                    <button
                      @click="provideFeedback(paper.paper_id, 'dislike')"
                      class="inline-flex items-center p-2 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900 rounded-md"
                      title="不喜欢这个推荐"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10H9a2 2 0 00-2 2v6a2 2 0 002 2h2.5" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 真值推荐分页条（仅真值页显示） -->
        <div
          v-if="activeTab === 'truth' && truthTotal > truthPageSize"
          class="mt-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
        >
          <div class="text-sm text-gray-600 dark:text-gray-300">
            共 <strong>{{ truthTotal }}</strong> 篇 ·
            第 <strong>{{ truthPage }}</strong> / <strong>{{ truthTotalPages }}</strong> 页
          </div>

          <div class="flex items-center gap-2">
            <button
              class="px-3 py-1 rounded-md border text-sm disabled:opacity-50"
              :disabled="truthPage <= 1"
              @click="prevTruthPage"
            >
              上一页
            </button>

            <!-- 简洁页码：当前页前后各显示一个 -->
            <button
              v-for="p in [truthPage - 1, truthPage, truthPage + 1].filter(n => n >= 1 && n <= truthTotalPages)"
              :key="p"
              class="px-3 py-1 rounded-md border text-sm"
              :class="p === truthPage ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-gray-50 dark:hover:bg-gray-700'"
              @click="goToTruthPage(p)"
            >
              {{ p }}
            </button>

            <button
              class="px-3 py-1 rounded-md border text-sm disabled:opacity-50"
              :disabled="truthPage >= truthTotalPages"
              @click="nextTruthPage"
            >
              下一页
            </button>

            <!-- 跳转到第几页 -->
            <div class="ml-2 flex items-center text-sm">
              <span class="mr-2">跳转到</span>
              <input
                type="number"
                min="1"
                :max="truthTotalPages"
                :value="truthPage"
                class="w-20 px-2 py-1 border rounded-md bg-white dark:bg-gray-700"
                @keyup.enter="goToTruthPage(($event.target as HTMLInputElement).valueAsNumber || truthPage)"
              />
              <span class="ml-1">/ {{ truthTotalPages }}</span>
            </div>
          </div>
        </div>


        <!-- 刷新推荐提示 -->
        <div v-if="activeTab !== 'truth' && recommendations.length >= 20" class="mt-8 text-center">
          <div class="card p-4">
            <svg class="inline-block w-5 h-5 text-blue-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <span class="text-blue-700 dark:text-blue-300">
              想看更多推荐？点击上方的"刷新推荐"按钮获取新的个性化推荐结果
            </span>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading" class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-white">暂无推荐内容</h3>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {{ 
            activeTab === 'daily' ? '请先阅读一些论文或添加收藏，以便我们为您生成日常推荐。' :
            activeTab === 'preference' ? '请先收藏一些论文，以便我们分析您的研究偏好。' :
            '暂时没有热门推荐内容。'
          }}
        </p>
        <div class="mt-6">
          <button
            @click="$router.push('/papers')"
            class="btn-primary"
          >
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            浏览论文库
          </button>
        </div>
      </div>
    </div>

    <!-- 推荐统计模态框 -->
    <div v-if="showStats" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50" @click="showStats = false">
      <div class="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white dark:bg-gray-800" @click.stop>
        <div class="mt-3">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-medium text-gray-900 dark:text-white">推荐统计</h3>
            <button @click="showStats = false" class="text-gray-400 hover:text-gray-600">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div v-if="stats" class="space-y-4">
            <div class="bg-blue-50 dark:bg-blue-900 p-3 rounded-lg">
              <div class="text-sm font-medium text-blue-800 dark:text-blue-200">用户画像完整度</div>
              <div class="mt-1 text-2xl font-bold text-blue-600 dark:text-blue-400">
                {{ (stats.user_profile_completeness * 100).toFixed(0) }}%
              </div>
            </div>
            
            <div class="bg-green-50 dark:bg-green-900 p-3 rounded-lg">
              <div class="text-sm font-medium text-green-800 dark:text-green-200">推荐准确度估计</div>
              <div class="mt-1 text-2xl font-bold text-green-600 dark:text-green-400">
                {{ (stats.recommendation_accuracy_estimate * 100).toFixed(0) }}%
              </div>
            </div>
            
            <div class="bg-purple-50 dark:bg-purple-900 p-3 rounded-lg">
              <div class="text-sm font-medium text-purple-800 dark:text-purple-200">已生成推荐数</div>
              <div class="mt-1 text-2xl font-bold text-purple-600 dark:text-purple-400">
                {{ stats.total_recommendations_generated }}
              </div>
            </div>

            <div v-if="stats.top_recommended_topics && stats.top_recommended_topics.length > 0">
              <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-2">您的热门主题</h4>
              <div class="space-y-1">
                <div 
                  v-for="topic in stats.top_recommended_topics.slice(0, 3)"
                  :key="topic.topic"
                  class="flex justify-between text-sm"
                >
                  <span class="text-gray-600 dark:text-gray-300">{{ topic.topic }}</span>
                  <span class="font-medium text-gray-900 dark:text-white">{{ topic.score }}</span>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else class="text-center py-4">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">加载统计数据...</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { api } from '@/services/api'

// —— 真值推荐分页状态（每页 20） ——
const truthPage = ref(1)
const truthPageSize = 20
const truthTotal = ref(0)

const truthTotalPages = computed(() =>
  Math.max(1, Math.ceil(truthTotal.value / truthPageSize))
)

function goToTruthPage(p: number) {
  const page = Math.min(Math.max(1, p), truthTotalPages.value)
  if (page !== truthPage.value) {
    truthPage.value = page
    loadRecommendations()
  }
}
function prevTruthPage() { goToTruthPage(truthPage.value - 1) }
function nextTruthPage() { goToTruthPage(truthPage.value + 1) }

const router = useRouter()
const userStore = useUserStore()

// 响应式数据
const loading = ref(false)
// 移除了 loadingMore 变量 - 不再需要分页功能
const error = ref<string | null>(null)
const recommendations = ref<any[]>([])
const trendingTopics = ref<any[]>([])
const stats = ref<any>(null)
const showStats = ref(false)
const activeTab = ref('daily')

// 标签页配置
const tabs = [
  { key: 'daily', name: '日常推荐' },
  { key: 'preference', name: '喜好推荐' },
  { key: 'popular', name: '热门推荐' },
  { key: 'truth', name: '真值推荐' },
]

// 计算属性
const averageRelevanceScore = computed(() => {
  if (recommendations.value.length === 0) return 0
  const sum = recommendations.value.reduce((acc, paper) => acc + paper.relevance_score, 0)
  return sum / recommendations.value.length
})

// 生命周期
onMounted(() => {
  loadRecommendations()
  loadTrendingTopics()
})

// 监听活跃标签页变化
watch(activeTab, () => {
  recommendations.value = []
  if (activeTab.value === 'truth') truthPage.value = 1  // ← 新增：切到真值页时回到第1页
  loadRecommendations()
})

// 监听统计模态框显示状态
watch(showStats, (show) => {
  if (show && !stats.value) {
    loadStats()
  }
})

// 方法
const loadRecommendations = async () => {
  if (!userStore.isAuthenticated && (activeTab.value === 'daily' || activeTab.value === 'preference')) {
    router.push('/login')
    return
  }

  loading.value = true
  error.value = null
  
  try {
    let response: any = null
    if (activeTab.value === 'daily') {
      response = await api.recommendations.getDaily({
        limit: 20,
        include_reasons: true
      })
    } else if (activeTab.value === 'preference') {
      response = await api.recommendations.getPreference({
        limit: 20,
        include_reasons: true
      })
    } else if (activeTab.value === 'popular') {
      response = await api.recommendations.getPopular({
        limit: 20
      })
    }
    else if (activeTab.value === 'truth') {
      const limit = truthPageSize
      const offset = (truthPage.value - 1) * truthPageSize
      const resp = await api.recommendations.getTruth({ limit, offset })
      const items = (resp.data?.items ?? []) as any[]
      truthTotal.value = resp.data?.total ?? items.length  // 记录总数

      recommendations.value = items.map(it => {
        const truthText = it.truth_value_text ?? `${((it.truth_value ?? 0) * 100).toFixed(1)}分`
        return {
          ...it,
          paper_id: it.short_id || it.id,
          relevance_score: it.truth_value ?? 0,
          importance_score: Math.max(0, Math.min(1, (it.fwci ?? 0) / 10)),
          recommendation_reason: `按真值从高到低排序（${truthText}）`,
        }
      })
    }
    
    if (activeTab.value !== 'truth' && response) {
      recommendations.value = response.data || []
    }
  } catch (err: any) {
    console.error('加载推荐失败:', err)
    error.value = err.response?.data?.detail || '加载推荐失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const loadTrendingTopics = async () => {
  try {
    const response = await api.recommendations.getTrendingTopics({
      limit: 10
    })
    trendingTopics.value = response.data || []
  } catch (err) {
    console.error('加载热门主题失败:', err)
  }
}

const loadStats = async () => {
  if (!userStore.isAuthenticated) return
  
  try {
    const response = await api.recommendations.getStats()
    stats.value = response.data
  } catch (err) {
    console.error('加载统计数据失败:', err)
  }
}

const refreshRecommendations = async () => {
  if (!userStore.isAuthenticated) {
    router.push('/login')
    return
  }
  
  try {
    loading.value = true
    await api.recommendations.refresh()
    setTimeout(() => {
      loadRecommendations()
    }, 2000) // 等待后台处理完成
  } catch (err) {
    console.error('刷新推荐失败:', err)
    error.value = '刷新推荐失败，请稍后重试'
    loading.value = false
  }
}

// 移除了 loadMoreRecommendations 函数 - 改用刷新推荐代替分页

const viewPaper = (paper: any) => {
  // 优先使用 short_id，如果没有则使用 paper_id
  const id = paper.short_id || paper.paper_id
  console.log('调试信息 - 论文数据:', paper)
  console.log('调试信息 - short_id:', paper.short_id) 
  console.log('调试信息 - paper_id:', paper.paper_id)
  console.log('调试信息 - 最终使用的ID:', id)
  router.push(`/papers/${id}`)
}

const provideFeedback = async (paperId: string, feedbackType: string) => {
  if (!userStore.isAuthenticated) {
    router.push('/login')
    return
  }
  
  try {
    await api.recommendations.provideFeedback(paperId, feedbackType)
    
    // 显示反馈成功提示
    // 这里可以添加 toast 通知
    console.log(`反馈已提交: ${feedbackType} for ${paperId}`)
  } catch (err) {
    console.error('提交反馈失败:', err)
  }
}
</script>

<style scoped>
/* 自定义样式 */
.bg-gradient-to-br {
  background: linear-gradient(to bottom right, var(--tw-gradient-stops));
}

/* 确保深色模式下的渐变效果 */
.dark .bg-gradient-to-br {
  background: linear-gradient(to bottom right, #111827, #1f2937, #111827);
}
</style>

