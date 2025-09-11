
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'
import { useUserStore } from '@/stores/user'
import type { TruthResponse } from '@/types'

// API基础配置
// 默认使用相对路径，通过Vite代理到后端，避免开发环境的CORS问题
const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || '/api'


// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(

  (config: InternalAxiosRequestConfig) => {
    const userStore = useUserStore()
    const token = userStore.token
    
    if (token) {
      // headers 可能是未定义或多种类型，使用安全写法
      config.headers = config.headers || {}
      // @ts-ignore - assign Authorization header
      config.headers.Authorization = `Bearer ${token}`
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  (error) => {
    const userStore = useUserStore()
    
    if (error.response?.status === 401) {
      // 只有在非论文详情页面时才跳转到登录页
      const currentPath = window.location.pathname
      if (!currentPath.includes('/papers/')) {
        userStore.logout()
        window.location.href = '/login'
      }
    }
    
    return Promise.reject(error)
  }
)

// API方法封装
export const api = {
  // 认证相关
  auth: {
    register: (userData: any) => apiClient.post('/auth/register', userData),
    login: (credentials: any) => apiClient.post('/auth/login', credentials),
    getProfile: () => apiClient.get('/auth/me'),
    updateProfile: (data: any) => apiClient.put('/auth/me', data),
    changePassword: (data: any) => apiClient.post('/auth/change-password', data),
  },

  // 搜索相关
  search: {
    papers: (searchData: any) => apiClient.post('/search/', searchData),
    suggestions: (query: string) => apiClient.get(`/search/suggestions?q=${query}`),
    filters: () => apiClient.get('/search/filters'),
    trending: () => apiClient.get('/search/trending'),
    history: () => apiClient.get('/search/history'),
  },

  // 论文相关
  papers: {
    list: (params: any) => apiClient.get('/papers/', { params }),
    get: (id: string) => apiClient.get('/papers/detail', { params: { paper_id: id } }),
    truthValue: (id: string) => apiClient.get('/papers/truth-value', { params: { paper_id: id } }),
    references: (id: string) => apiClient.get('/papers/references', { params: { paper_id: id } }),
    citations: (id: string) => apiClient.get('/papers/citations', { params: { paper_id: id } }),
    similar: (id: string) => apiClient.get('/papers/similar', { params: { paper_id: id } }),
    bookmark: (id: string) => apiClient.post('/papers/bookmark', {}, { params: { paper_id: id } }),
    unbookmark: (id: string) => apiClient.delete('/papers/bookmark', { params: { paper_id: id } }),
    compare: (id1: string, id2: string) => apiClient.post('/papers/compare', { paper_id1: id1, paper_id2: id2 }),
    citationNetwork: (id: string) => apiClient.get('/papers/citation-network', { params: { paper_id: id } }),
    citationGraph: (id: string, params?: any) => apiClient.get('/papers/citation-graph', { params: { paper_id: id, ...params } }),
  },

  // 作者相关
  authors: {
    list: (params: any) => apiClient.get('/authors/', { params }),
    get: (id: string) => apiClient.get(`/authors/${id}`),
    papers: (id: string, params?: any) => apiClient.get(`/authors/${id}/papers`, { params }),
    statistics: (id: string) => apiClient.get(`/authors/${id}/statistics`),
    timeline: (id: string) => apiClient.get(`/authors/${id}/career-timeline`),
    evolution: (id: string) => apiClient.get(`/authors/${id}/research-evolution`),
    network: (id: string) => apiClient.get(`/authors/${id}/collaboration-network`),
    graph: (id: string, params?: any) => apiClient.get(`/authors/${id}/graph`, { params }),
    follow: (id: string) => apiClient.post(`/authors/${id}/follow`),
    unfollow: (id: string) => apiClient.delete(`/authors/${id}/follow`),
  },

  // 工作台相关
  workspace: {
    dashboard: () => apiClient.get('/workspace/dashboard'),
    bookmarks: (params?: any) => apiClient.get('/workspace/bookmarks', { params }),
    folders: () => apiClient.get('/workspace/folders'),
    createFolder: (data: any) => apiClient.post('/workspace/folders', data),
    updateFolder: (id: string, data: any) => apiClient.put(`/workspace/folders/${id}`, data),
    deleteFolder: (id: string) => apiClient.delete(`/workspace/folders/${id}`),
    addToFolder: (folderId: string, paperId: string) => 
      apiClient.post(`/workspace/folders/${folderId}/papers/${paperId}`),
    removeFromFolder: (folderId: string, paperId: string) => 
      apiClient.delete(`/workspace/folders/${folderId}/papers/${paperId}`),
    followedAuthors: () => apiClient.get('/workspace/followed-authors'),
    readingHistory: (params?: any) => apiClient.get('/workspace/reading-history', { params }),
    addReading: (paperId: string) => apiClient.post(`/workspace/reading-history/${paperId}`),
    recommendations: (params?: any) => apiClient.get('/workspace/recommendations', { params }),
    stats: () => apiClient.get('/workspace/stats'),
  },

  // AI助手相关
  ai: {
    summarize: (paperId: string) => apiClient.post(`/ai-assistant/summarize/${paperId}`),
    compare: (paperIds: string[]) => apiClient.post('/ai-assistant/compare', { paper_ids: paperIds }),
    trends: (field: string) => apiClient.post('/ai-assistant/research-trends', { research_field: field }),
    explain: (paperId: string, aspect: string) => 
      apiClient.post(`/ai-assistant/explain-paper/${paperId}?aspect=${aspect}`),
    recommend: (paperId: string, limit?: number) => 
      apiClient.post(`/ai-assistant/recommend-readings/${paperId}`, { limit }),
    ideas: (paperId: string) => apiClient.post(`/ai-assistant/generate-research-ideas/${paperId}`),
    capabilities: () => apiClient.get('/ai-assistant/capabilities'),
  },

  // 智能推荐相关
  recommendations: {
    getPersonalized: (params?: any) => apiClient.get('/recommendations/', { params }),
    getDaily: (params?: any) => apiClient.get('/recommendations/daily', { params }),
    getPreference: (params?: any) => apiClient.get('/recommendations/preference', { params }),
    getPopular: (params?: any) => apiClient.get('/recommendations/popular', { params }),
    getTrendingTopics: (params?: any) => apiClient.get('/recommendations/trending-topics', { params }),
    getStats: () => apiClient.get('/recommendations/stats'),
    getSimilar: (paperId: string, params?: any) => apiClient.get(`/recommendations/similar/${paperId}`, { params }),
    provideFeedback: (paperId: string, feedbackType: string) => 
      apiClient.post('/recommendations/feedback', null, { params: { paper_id: paperId, feedback_type: feedbackType } }),
    refresh: () => apiClient.post('/recommendations/refresh'),
    getTruth: (params?: { limit?: number; offset?: number }) => apiClient.get<TruthResponse>('/truth_value/', { params }),  },

  // 系统状态相关
  system: {
    status: () => apiClient.get('/system/status'),
    health: () => apiClient.get('/health')
  }
}

export default apiClient

