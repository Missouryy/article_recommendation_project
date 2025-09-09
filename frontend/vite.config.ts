import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { silentProxyPlugin } from './vite-plugin-silent-proxy.js'

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    // 抑制Node.js deprecation警告
    'process.env.NODE_OPTIONS': JSON.stringify('--no-deprecation')
  },
  plugins: [vue(), silentProxyPlugin()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@components': resolve(__dirname, 'src/components'),
      '@views': resolve(__dirname, 'src/views'),
      '@stores': resolve(__dirname, 'src/stores'),
      '@services': resolve(__dirname, 'src/services'),
      '@utils': resolve(__dirname, 'src/utils'),
      '@types': resolve(__dirname, 'src/types'),
      '@assets': resolve(__dirname, 'src/assets')
    }
  },
  server: {
    host: '0.0.0.0',  // 绑定到所有地址
    port: 5173,
    open: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        timeout: 5000,
        configure: (proxy, options) => {
          // 完全静默处理所有代理错误
          proxy.on('error', (err: any, req, res) => {
            // 静默处理，不输出任何错误到控制台
            res.writeHead(503, {
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*',
              'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
              'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            })
            res.end(JSON.stringify({ 
              error: 'Backend not ready',
              code: 'ECONNREFUSED',
              message: '后端服务尚未启动'
            }))
          })
        }
      }
    }
  },
  build: {
    target: 'es2015',
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          charts: ['echarts', 'd3', '@antv/g6'],
          utils: ['axios', 'dayjs', 'lodash-es']
        }
      }
    }
  },
  optimizeDeps: {
    include: ['vue', 'vue-router', 'pinia', 'axios', 'dayjs', 'lodash-es']
  }
})

