"""
AI 总结 API 接口
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from ..api.auth import get_current_user
from ..models.user import User
from ..services.gemini_service import gemini_service
from ..db.database import db

router = APIRouter(prefix="/ai", tags=["AI 总结"])

@router.get("/summary/{paper_id}", summary="获取论文AI总结")
async def get_paper_summary(
    paper_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取论文的AI总结
    
    - **paper_id**: 论文ID
    """
    try:
        # 获取论文详细信息
        paper = await db.get_paper_by_id(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        
        # 检查 Gemini API 是否配置
        if not gemini_service.is_configured():
            raise HTTPException(
                status_code=503, 
                detail="AI 总结服务暂不可用，请检查 Gemini API 配置"
            )
        
        # 调用 AI 总结服务
        result = await gemini_service.summarize_paper(paper)
        
        if result["success"]:
            return {
                "success": True,
                "summary": result["summary"],
                "paper_id": paper_id,
                "paper_title": paper.get("title", "")
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"AI 总结失败: {result['error']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取论文总结时发生错误: {str(e)}"
        )

@router.get("/analysis/{paper_id}", summary="获取论文质量分析")
async def get_paper_analysis(
    paper_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取论文的质量分析
    
    - **paper_id**: 论文ID
    """
    try:
        # 获取论文详细信息
        paper = await db.get_paper_by_id(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        
        # 检查 Gemini API 是否配置
        if not gemini_service.is_configured():
            raise HTTPException(
                status_code=503, 
                detail="AI 分析服务暂不可用，请检查 Gemini API 配置"
            )
        
        # 调用 AI 质量分析服务
        result = await gemini_service.analyze_paper_quality(paper)
        
        if result["success"]:
            return {
                "success": True,
                "analysis": result["analysis"],
                "paper_id": paper_id,
                "paper_title": paper.get("title", "")
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"AI 分析失败: {result['error']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取论文分析时发生错误: {str(e)}"
        )

@router.get("/status", summary="检查AI服务状态")
async def check_ai_status():
    """
    检查 AI 服务状态
    """
    is_configured = gemini_service.is_configured()
    
    return {
        "ai_service_available": is_configured,
        "service_name": "Gemini AI",
        "message": "AI 服务已就绪" if is_configured else "AI 服务未配置，请在配置文件中设置 Gemini API key"
    }

