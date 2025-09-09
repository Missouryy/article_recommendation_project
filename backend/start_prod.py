#!/usr/bin/env python3
"""
生产环境启动脚本
优化的生产配置
"""
import uvicorn
import logging
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置生产环境日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    print("🚀 启动学术论文推荐系统生产服务器...")
    print("📝 配置信息:")
    print("   - 主机: 0.0.0.0")
    print("   - 端口: 8000")
    print("   - 热重载: 已禁用")
    print("   - 日志级别: INFO")
    print("   - 工作进程: 4")
    print()
    
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info",
            workers=4,  # 多进程处理
            use_colors=False,
            access_log=True,
            # 生产环境性能优化
            loop="uvloop",  # 使用更快的事件循环
            http="httptools"  # 使用更快的HTTP解析器
        )
    except KeyboardInterrupt:
        print("\n✅ 服务器已安全关闭")
    except Exception as e:
        print(f"\n❌ 服务器启动失败: {e}")
        sys.exit(1)

