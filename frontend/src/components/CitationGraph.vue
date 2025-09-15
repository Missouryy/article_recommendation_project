<template>
  <div class="citation-graph-container">
    <!-- 控制面板 -->
    <div class="graph-controls mb-4">
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex items-center gap-2">
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300">深度:</label>
          <div class="relative">
            <select 
              v-model="graphDepth" 
              @change="updateGraph"
              class="w-18 px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="1">1层</option>
              <option value="2">2层</option>
              <option value="3">3层</option>
            </select>
          </div>
        </div>
        
        <div class="flex items-center gap-2">
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300">最大节点:</label>
          <div class="relative">
            <select 
              v-model="maxNodes" 
              @change="updateGraph"
              class="w-16 px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="30">30</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
        </div>
        
        <button 
          @click="resetZoom"
          class="btn-secondary text-sm px-3 py-1"
        >
          重置视图
        </button>
        
        <button 
          @click="toggleLayout"
          class="btn-primary text-sm px-3 py-1"
        >
          {{ currentLayout === 'force' ? '切换为环形布局' : '切换为力导向布局' }}
        </button>
      </div>
    </div>

    <!-- 图例 -->
    <div class="graph-legend mb-4">
      <div class="flex flex-wrap items-center gap-4 text-sm">
        <div class="flex items-center gap-2">
          <div class="w-4 h-4 rounded-full bg-blue-500"></div>
          <span class="text-gray-700 dark:text-gray-300">中心论文</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="w-4 h-4 rounded-full bg-green-500"></div>
          <span class="text-gray-700 dark:text-gray-300">被引文献</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="w-4 h-4 rounded-full bg-orange-500"></div>
          <span class="text-gray-700 dark:text-gray-300">参考文献</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="w-4 h-4 rounded-full bg-purple-500"></div>
          <span class="text-gray-700 dark:text-gray-300">二级关系</span>
        </div>
      </div>
    </div>

    <!-- 图谱容器（包裹层用于覆盖） -->
    <div class="relative">
      <div 
        ref="graphContainer" 
        class="graph-container card w-full h-96"
      ></div>

      <!-- 高级加载进度覆盖层：半透明暗色背景 + 中央环形进度 -->
      <div v-if="loading" class="absolute inset-0 z-10">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-[1px] rounded-lg"></div>
        <div class="relative z-10 w-full h-full flex flex-col items-center justify-center select-none">
          <div 
            class="w-28 h-28 rounded-full shadow-inner"
            :style="{ 
              background: `conic-gradient(#3B82F6 ${Math.min(100, Math.max(0, loadProgress))*3.6}deg, rgba(255,255,255,0.15) ${Math.min(100, Math.max(0, loadProgress))*3.6}deg)`
            }"
          >
            <div class="w-24 h-24 m-2 rounded-full bg-white/90 dark:bg-gray-800/90 flex items-center justify-center">
              <div class="text-xl font-semibold text-gray-800 dark:text-gray-100">{{ Math.round(loadProgress) }}%</div>
            </div>
          </div>
          <div class="mt-3 text-sm text-white/90">正在加载引用图谱...</div>
        </div>
      </div>
    </div>

    <!-- 论文详情弹窗 -->
    <div 
      v-if="selectedPaper"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      @click="closePaperDetail"
    >
      <div 
        class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto"
        @click.stop
      >
        <div class="p-6">
          <div class="flex justify-between items-start mb-4">
            <h3 class="text-xl font-bold text-gray-900 dark:text-white">
              {{ (selectedPaper as any)?.title || (selectedPaper as any)?.label || '未命名论文' }}
            </h3>
            <button 
              @click="closePaperDetail"
              class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
          
          <div class="space-y-3 text-sm text-gray-700 dark:text-gray-300">
            <div>
              <span class="font-medium">作者:</span> {{ Array.isArray((selectedPaper as any)?.authors) ? (selectedPaper as any).authors.join(', ') : '' }}
            </div>
            <div>
              <span class="font-medium">年份:</span> {{ (selectedPaper as any)?.year ?? '' }}
            </div>
            <div>
              <span class="font-medium">期刊:</span> {{ (selectedPaper as any)?.journal ?? '' }}
            </div>
            <div>
              <span class="font-medium">引用数:</span> {{ (selectedPaper as any)?.citation_count ?? '' }}
            </div>
            <div>
              <span class="font-medium">摘要:</span>
              <p class="mt-1 text-gray-600 dark:text-gray-400">{{ (selectedPaper as any)?.abstract || '' }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

interface GraphNode {
  id: string
  label: string
  type: string
  size: number
  color: string
  metadata: {
    title: string
    authors: string[]
    year: number
    journal: string
    abstract: string
    citation_count: number
  }
}

interface GraphEdge {
  source: string
  target: string
  type: string
  weight: number
  metadata: any
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  center_node: string
  layout: string
}

interface Props {
  paperId: string
}

const props = defineProps<Props>()

// 响应式数据
const graphContainer = ref<HTMLElement>()
const graphDepth = ref(2)
const maxNodes = ref(30)
const currentLayout = ref('force')
const selectedPaper = ref<GraphNode | null>(null)
const loading = ref(false)
const loadProgress = ref(0)

// D3相关变量
let svg: any = null
let simulation: any = null
let zoom: any = null

// 监听paperId变化
watch(() => props.paperId, (newId) => {
  if (newId) {
    updateGraph()
  }
})

// 更新图谱
const updateGraph = async () => {
  if (!props.paperId) return
  
  try {
    loading.value = true
    loadProgress.value = 0
    const targetDepth = Number(graphDepth.value)
    const firstDepth = 1
    // 阶段1：先拉取 depth=1，快速渲染
    const res1 = await fetch(`/api/papers/citation-graph?paper_id=${encodeURIComponent(props.paperId)}&depth=${firstDepth}&max_nodes=${maxNodes.value}`)
    const data1: GraphData = await res1.json()
    // 无论 nodes 是否为空，先渲染一次：renderGraph 内部会保障中心节点存在
    let bestData: GraphData | null = data1
    let bestCount = Array.isArray(data1.nodes) ? data1.nodes.length : 0
    renderGraph(data1)
    loadProgress.value = targetDepth > 1 ? 30 : 100

    // 阶段2：轮询目标深度，直到节点数增长或超时
    if (targetDepth > 1) {
      const totalMs = 15000  // 减少超时时间到15秒
      const deadline = Date.now() + totalMs
      let lastCount = bestCount
      let noProgressCount = 0
      
      while (Date.now() < deadline) {
        try {
          const res = await fetch(`/api/papers/citation-graph?paper_id=${encodeURIComponent(props.paperId)}&depth=${targetDepth}&max_nodes=${maxNodes.value}`)
          const data: GraphData = await res.json()
          const count = Array.isArray(data.nodes) ? data.nodes.length : 0
          const elapsed = 1 - Math.max(0, deadline - Date.now()) / totalMs
          loadProgress.value = Math.min(95, 30 + elapsed * 65)
          
          // 检查是否有进展
          if (count > lastCount) {
            lastCount = count
            noProgressCount = 0
            bestData = data
            bestCount = count
            renderGraph(data)
          } else {
            noProgressCount++
            // 如果连续3次没有进展，提前结束
            if (noProgressCount >= 3) {
              console.log('引用图谱构建完成，提前结束轮询')
              break
            }
          }
        } catch (e) {
          // 忽略临时失败，继续轮询
        }
        await new Promise(r => setTimeout(r, 1000))  // 增加轮询间隔到1秒
      }
      // 最后一轮保证显示最新数据并收尾
      loadProgress.value = 100
      if (bestData) {
        renderGraph(bestData)
      }
    }
  } catch (error) {
    console.error('获取引用图谱失败:', error)
  }
  finally {
    // 收尾隐藏（确保不会卡在30%）
    setTimeout(() => {
      loading.value = false
      loadProgress.value = 0
    }, 300)
  }
}

// 渲染图谱
const renderGraph = (data: GraphData) => {
  if (!graphContainer.value) return
  // 保证中心节点存在：如果缺失，注入一个最小信息的中心节点
  const centerId = data.center_node
  if (!Array.isArray(data.nodes) || data.nodes.length === 0 || !data.nodes.some(n => n.id === centerId)) {
    const fallback: GraphNode = {
      id: centerId,
      label: '中心论文',
      type: 'paper',
      size: 20,
      color: '#3B82F6',
      metadata: {
        title: '中心论文',
        authors: [],
        year: 0,
        journal: '',
        abstract: '',
        citation_count: 0
      }
    }
    data = {
      ...data,
      nodes: [fallback, ...(data.nodes || [])],
      edges: data.edges || []
    }
  }
  
  // 清除现有内容
  d3.select(graphContainer.value).selectAll('*').remove()
  
  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  
  // 创建SVG
  svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
  
  // 创建缩放功能
  zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      svg.select('.graph-group').attr('transform', event.transform)
    })
  
  svg.call(zoom)
  
  // 创建主图形组
  const g = svg.append('g').attr('class', 'graph-group')
  
  // 处理边数据
  const links = (data.edges || []).map(edge => ({
    source: edge.source,
    target: edge.target,
    weight: edge.weight
  }))
  
  // 处理节点数据：扁平化 metadata，避免模板读取字段时未定义
  const nodes = (data.nodes || []).map(node => ({
    ...node,
    ...(node as any).metadata,
    x: Math.random() * width,
    y: Math.random() * height
  }))
  
  // 创建箭头标记
  g.append('defs').selectAll('marker')
    .data(['citation'])
    .enter().append('marker')
    .attr('id', (d: any) => d)
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 20)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#999')
  
  // 创建边
  const link = g.append('g')
    .selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke', '#999')
    .attr('stroke-opacity', 0.6)
    .attr('stroke-width', (d: any) => Math.sqrt(d.weight) * 2)
    .attr('marker-end', 'url(#citation)')
  
  // 创建节点
  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .enter().append('g')
    .attr('class', 'node')
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended)
    )
    .on('click', (_event: any, d: any) => showPaperDetail(d))
  
  // 添加节点圆圈
  node.append('circle')
    .attr('r', (d: any) => d.size)
    .attr('fill', (d: any) => d.color)
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)
    .attr('stroke-opacity', 0.8)
  
  // 添加节点标签
  node.append('text')
    .text((d: any) => truncateLabel(d.label, 10))
    .attr('text-anchor', 'middle')
    .attr('dy', (d: any) => d.size + 15)
    .attr('font-size', '10px')
    .attr('fill', '#333')
    .attr('pointer-events', 'none')
  
  // 创建力导向模拟
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id((d: any) => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius((d: any) => d.size + 5))
  
  // 更新位置
  simulation.on('tick', () => {
    link
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)
    
    node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })
}

// 拖拽事件处理
const dragstarted = (event: any, d: any) => {
  if (!event.active) simulation.alphaTarget(0.3).restart()
  d.fx = d.x
  d.fy = d.y
}

const dragged = (event: any, d: any) => {
  d.fx = event.x
  d.fy = event.y
}

const dragended = (event: any, d: any) => {
  if (!event.active) simulation.alphaTarget(0)
  d.fx = null
  d.fy = null
}

// 截断标签，避免过长显示
const truncateLabel = (text: string, maxLen: number) => {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen - 1) + '…'
}

// 显示论文详情
const showPaperDetail = (paper: GraphNode) => {
  selectedPaper.value = paper
}

// 关闭论文详情
const closePaperDetail = () => {
  selectedPaper.value = null
}

// 重置缩放
const resetZoom = () => {
  if (svg && zoom) {
    svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity)
  }
}

// 切换布局
const toggleLayout = () => {
  currentLayout.value = currentLayout.value === 'force' ? 'circle' : 'force'
  updateGraph()
}

// 组件挂载时初始化
onMounted(() => {
  if (props.paperId) {
    updateGraph()
  }
  
  // 监听窗口大小变化
  const handleResize = () => {
    if (graphContainer.value) {
      updateGraph()
    }
  }
  
  window.addEventListener('resize', handleResize)
  
  // 清理函数
  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    if (simulation) {
      simulation.stop()
    }
  })
})
</script>

<style scoped>
.citation-graph-container {
  @apply w-full;
}

.graph-container {
  @apply relative;
}

.graph-container svg {
  @apply w-full h-full;
}

.node {
  @apply cursor-pointer;
}

.node:hover circle {
  @apply stroke-2 stroke-blue-500;
}

.node:hover text {
  @apply font-semibold;
}
</style>
