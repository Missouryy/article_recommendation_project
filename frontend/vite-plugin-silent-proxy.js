// Vite插件：静默处理代理错误
export function silentProxyPlugin() {
  return {
    name: 'silent-proxy',
    configureServer(server) {
      // 拦截所有代理错误，静默处理
      server.middlewares.use('/api', (req, res, next) => {
        const originalWrite = res.write
        const originalEnd = res.end
        
        // 重写write方法，过滤错误日志
        res.write = function(chunk, encoding, callback) {
          if (chunk && typeof chunk === 'string' && 
              (chunk.includes('ECONNREFUSED') || chunk.includes('Backend not ready'))) {
            // 静默处理，不输出到控制台
            return true
          }
          return originalWrite.call(this, chunk, encoding, callback)
        }
        
        // 重写end方法
        res.end = function(chunk, encoding, callback) {
          if (chunk && typeof chunk === 'string' && 
              (chunk.includes('ECONNREFUSED') || chunk.includes('Backend not ready'))) {
            // 静默处理
            return this
          }
          return originalEnd.call(this, chunk, encoding, callback)
        }
        
        next()
      })
      
      // 拦截控制台输出，过滤ECONNREFUSED错误
      const originalConsoleError = console.error
      console.error = function(...args) {
        const message = args.join(' ')
        if (message.includes('ECONNREFUSED') || 
            message.includes('http proxy error') ||
            message.includes('Backend not ready')) {
          // 静默处理，不输出
          return
        }
        originalConsoleError.apply(console, args)
      }
    }
  }
}
