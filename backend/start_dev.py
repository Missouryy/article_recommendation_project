#!/usr/bin/env python3
"""
开发环境启动脚本
优化的启动配置，减少警告信息
"""
import uvicorn
import logging
import sys
import os
import webbrowser
import threading
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志级别，减少不必要的警告
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def open_api_docs():
    """延迟打开API文档"""
    time.sleep(5)  # 等待服务器完全启动
    # 检查服务器是否真的启动了
    try:
        import requests
        response = requests.get('http://127.0.0.1:8000/health', timeout=5)
        if response.status_code == 200:
            print("🌐 自动打开API文档...")
            webbrowser.open('http://127.0.0.1:8000/docs')
        else:
            print("⚠️ 服务器还未完全启动，跳过自动打开")
    except Exception as e:
        print(f"⚠️ 服务器尚未启动，跳过自动打开: {e}")
        print("💡 请等待服务器启动后手动访问: http://127.0.0.1:8000/docs")

if __name__ == "__main__":
    print("🚀 启动学术论文推荐系统开发服务器...")
    print("📝 配置信息:")
    print("   - 主机: 127.0.0.1")
    print("   - 端口: 8000")
    print("   - 热重载: 已启用")
    print("   - 日志级别: 优化")
    print("   - API文档: http://127.0.0.1:8000/docs")
    print("   - 自动打开: 已启用")
    print()
    
    # 暂时禁用自动打开功能来调试启动问题
    # threading.Thread(target=open_api_docs, daemon=True).start()
    
    try:
        # 确保在正确的目录中启动
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info",
            workers=1  # 开发环境使用单进程
        )
    except KeyboardInterrupt:
        print("\n✅ 服务器已安全关闭")
    except Exception as e:
        print(f"\n❌ 服务器启动失败: {e}")
        sys.exit(1)
