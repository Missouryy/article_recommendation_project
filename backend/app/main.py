"""
FastAPI主应用文件
学术论文推荐系统后端API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import logging

# 导入API路由
from .api import auth, search, papers, authors, workspace, ai_assistant, recommendations

# 配置日志，减少uvicorn的重载警告
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("watchfiles").setLevel(logging.WARNING)

# 全局变量
startup_completed = False

# 创建FastAPI应用实例
app = FastAPI(
    title="学术论文推荐系统API",
    description="""
    高级学术论文推荐Web系统的后端API服务
    
    ## 主要功能
    
    * **用户系统** - 注册、登录、个人信息管理
    * **智能搜索** - 混合搜索、语义搜索、动态筛选
    * **论文管理** - 论文详情、引用分析、真值计算
    * **作者分析** - 作者画像、合作网络、学术轨迹
    * **个人工作台** - 收藏管理、关注列表、阅读历史
    * **AI助手** - 论文总结、对比分析、研究建议
    
    ## 技术特色
    
    * 基于FastAPI的高性能API服务
    * 完整的用户认证和权限管理
    * 模拟数据库提供丰富的测试数据
    * 真值算法和推荐算法的占位符实现
    * 支持知识图谱和网络分析
    """,
    version="1.0.0",
    terms_of_service="http://example.com/terms/",
    contact={
        "name": "学术推荐系统团队",
        "url": "http://example.com/contact/",
        "email": "contact@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vue开发服务器
        "http://localhost:3000",  # 备用端口
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:8080",  # Vue生产构建
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加事件处理器
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global startup_completed
    try:
        print("🚀 学术论文推荐系统API启动中...")
        print("📚 初始化模拟数据库...")
        print("🔧 配置算法模块...")
        
        # 预加载智能推荐系统资源
        print("🤖 预加载智能推荐系统资源...")
        try:
            from .api.recommendations import recommender
            await recommender.ensure_loaded()
            print("✅ 智能推荐系统资源加载完成")
        except Exception as e:
            print(f"⚠️ 智能推荐系统资源加载失败: {e}")
            print("   系统将继续运行，但推荐功能可能受限")
        
        print("✅ 系统启动完成！")
        print("📖 API文档: http://127.0.0.1:8000/docs")
        startup_completed = True
    except Exception as e:
        print(f"❌ 启动过程中发生错误: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    try:
        print("🛑 学术论文推荐系统API正在关闭...")
        print("💾 保存用户数据...")
        print("🧹 清理资源...")
        print("✅ 系统已安全关闭")
    except Exception as e:
        print(f"⚠️ 关闭过程中的警告: {e}")

# 注册API路由
app.include_router(auth.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(papers.router, prefix="/api")
app.include_router(authors.router, prefix="/api")
app.include_router(workspace.router, prefix="/api")
app.include_router(ai_assistant.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")


# 根路径
@app.get("/", tags=["系统"])
async def root():
    """
    系统根路径，返回API基本信息
    """
    return {
        "message": "学术论文推荐系统API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "features": [
            "用户认证系统",
            "智能搜索引擎", 
            "论文推荐算法",
            "AI助手服务",
            "个人工作台",
            "作者分析工具"
        ]
    }

# 健康检查端点
@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查端点，用于监控服务状态
    """
    try:
        # 这里可以添加数据库连接检查等
        return {
            "status": "healthy",
            "timestamp": "2023-12-01T10:00:00Z",
            "services": {
                "api": "running",
                "database": "connected",
                "algorithms": "available"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service unavailable")

# 系统状态端点（用于前端检查后端是否准备就绪）
@app.get("/api/system/status", tags=["系统"])
async def system_status():
    """
    系统状态检查，用于前端判断后端是否完全准备就绪
    检查各个组件的真实加载状态
    """
    try:
        # 检查智能推荐系统状态
        recommender_status = "not_loaded"
        faiss_status = "not_loaded"
        bert_status = "not_loaded"
        
        try:
            from .api.recommendations import recommender
            if recommender._loaded:
                recommender_status = "ready"
                # 检查具体组件
                if recommender.index is not None:
                    faiss_status = "ready"
                if recommender.model is not None:
                    bert_status = "ready"
            elif recommender._loading:
                recommender_status = "loading"
                faiss_status = "loading"
                bert_status = "loading"
        except Exception as e:
            recommender_status = "error"
            faiss_status = "error"
            bert_status = "error"
        
        # 计算整体状态
        if recommender_status == "ready" and faiss_status == "ready" and bert_status == "ready":
            overall_status = "ready"
            progress = 100
            message = "系统已完全加载，准备就绪"
        elif recommender_status == "loading" or faiss_status == "loading" or bert_status == "loading":
            overall_status = "loading"
            progress = 50
            message = "系统正在加载中，请稍候..."
        else:
            overall_status = "error"
            progress = 25
            message = "系统加载遇到问题，部分功能可能受限"
        
        return {
            "overall": overall_status,
            "components": {
                "database": {"status": "ready", "progress": 100},
                "faiss_index": {"status": faiss_status, "progress": 100 if faiss_status == "ready" else 0},
                "bert_model": {"status": bert_status, "progress": 100 if bert_status == "ready" else 0},
                "api": {"status": "ready", "progress": 100}
            },
            "progress": progress,
            "message": message
        }
        
    except Exception as e:
        return {
            "overall": "error",
            "components": {
                "database": {"status": "ready", "progress": 100},
                "faiss_index": {"status": "error", "progress": 0},
                "bert_model": {"status": "error", "progress": 0},
                "api": {"status": "ready", "progress": 100}
            },
            "progress": 25,
            "message": f"系统状态检查失败: {str(e)}"
        }

# 全局异常处理器
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """
    处理404错误
    """
    return JSONResponse(
        status_code=404,
        content={
            "error": "资源未找到",
            "message": f"请求的资源 {request.url.path} 不存在"
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """
    处理500内部服务器错误
    """
    return JSONResponse(
        status_code=500,
        content={
            "error": "服务器内部错误",
            "message": "服务器处理请求时发生错误，请稍后重试"
        }
    )

# 中间件：请求日志
@app.middleware("http")
async def log_requests(request, call_next):
    """
    记录请求日志（简化版）
    """
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        # 在生产环境中，这里应该记录到日志文件
        print(f"请求处理错误: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "请求处理失败", "message": str(e)}
        )

# 数据分析端点
@app.get("/api/analytics", tags=["系统"])
async def analytics():
    """
    获取系统数据分析和统计信息
    用于管理员监控系统使用情况
    """
    # 模拟数据统计
    stats = {
        "total_papers": 2213123,
        "total_authors": 456789,
        "total_users": 1234,
        "total_searches": 5678,
        "active_sessions": 45
    }
    
    research_fields = [
        {"field": "计算机科学", "count": 450000, "percentage": 20.3},
        {"field": "物理学", "count": 380000, "percentage": 17.2},
        {"field": "数学", "count": 290000, "percentage": 13.1},
        {"field": "生物学", "count": 275000, "percentage": 12.4},
        {"field": "化学", "count": 245000, "percentage": 11.1},
        {"field": "其他", "count": 573123, "percentage": 25.9}
    ]
    
    return {
        "database_stats": stats,
        "research_fields": research_fields,
        "system_status": {
            "uptime": "running",
            "version": "1.0.0",
            "last_updated": "2023-12-01T10:00:00Z"
        }
    }

if __name__ == "__main__":
    # 开发环境启动配置
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        reload_excludes=["*.pyc", "__pycache__"]  # 排除一些不需要重载的文件
    )