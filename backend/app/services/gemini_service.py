"""
Gemini AI 服务模块
用于调用 Google Gemini API 进行论文总结和分析
"""
import json
import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from ..db.config import get_database_config

class GeminiService:
    """Gemini AI 服务类"""
    
    def __init__(self):
        self.api_key = None
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model_name = "gemini-1.5-flash"  # 使用最新的模型名称
        self._load_api_key()
    
    def _load_api_key(self):
        """从配置文件加载 API key"""
        try:
            config = get_database_config()
            self.api_key = config.get("gemini_api_key")
            if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
                print("警告: Gemini API key 未配置或使用默认值")
                self.api_key = None
        except Exception as e:
            print(f"加载 Gemini API key 失败: {e}")
            self.api_key = None
    
    def is_configured(self) -> bool:
        """检查 API key 是否已配置"""
        return self.api_key is not None and self.api_key != "YOUR_GEMINI_API_KEY_HERE"
    
    async def summarize_paper(self, paper_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        总结论文内容
        
        Args:
            paper_data: 论文数据，包含标题、摘要、关键词等
            
        Returns:
            包含总结结果的字典
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Gemini API key 未配置",
                "summary": None
            }
        
        try:
            # 构建提示词
            prompt = self._build_summary_prompt(paper_data)
            
            # 调用 Gemini API
            response = await self._call_gemini_api(prompt)
            
            if response.get("success"):
                return {
                    "success": True,
                    "summary": response.get("content"),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "API 调用失败"),
                    "summary": None
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"总结过程中发生错误: {str(e)}",
                "summary": None
            }
    
    def _build_summary_prompt(self, paper_data: Dict[str, Any]) -> str:
        """构建论文总结的提示词"""
        title = paper_data.get("title", "")
        abstract = paper_data.get("abstract", "")
        keywords = paper_data.get("keywords", [])
        authors = paper_data.get("author_names", [])
        journal = paper_data.get("journal", "")
        year = paper_data.get("year", "")
        
        # 构建关键词字符串
        keywords_str = ", ".join(keywords) if keywords else "无"
        
        # 构建作者字符串
        authors_str = ", ".join(authors) if authors else "未知作者"
        
        prompt = f"""
请对以下学术论文进行专业总结，要求：

1. 用中文回答
2. 总结要简洁明了，控制在200-300字
3. 重点突出论文的核心贡献和创新点
4. 分析论文的研究方法和主要发现
5. 评估论文的学术价值和实际意义

论文信息：
标题：{title}
作者：{authors_str}
期刊：{journal}
年份：{year}
关键词：{keywords_str}

摘要：
{abstract}

请提供专业的论文总结：
"""
        return prompt.strip()
    
    async def _call_gemini_api(self, prompt: str) -> Dict[str, Any]:
        """调用 Gemini API"""
        # 使用正确的 API 端点
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 解析响应
                        if "candidates" in result and len(result["candidates"]) > 0:
                            content = result["candidates"][0]["content"]["parts"][0]["text"]
                            return {
                                "success": True,
                                "content": content.strip()
                            }
                        else:
                            return {
                                "success": False,
                                "error": "API 返回格式异常"
                            }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"API 调用失败 (状态码: {response.status}): {error_text}"
                        }
                        
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"网络请求失败: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"API 调用异常: {str(e)}"
            }
    
    async def analyze_paper_quality(self, paper_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析论文质量
        
        Args:
            paper_data: 论文数据
            
        Returns:
            包含质量分析结果的字典
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Gemini API key 未配置",
                "analysis": None
            }
        
        try:
            # 构建质量分析提示词
            prompt = self._build_quality_analysis_prompt(paper_data)
            
            # 调用 Gemini API
            response = await self._call_gemini_api(prompt)
            
            if response.get("success"):
                return {
                    "success": True,
                    "analysis": response.get("content"),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "API 调用失败"),
                    "analysis": None
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"质量分析过程中发生错误: {str(e)}",
                "analysis": None
            }
    
    def _build_quality_analysis_prompt(self, paper_data: Dict[str, Any]) -> str:
        """构建论文质量分析的提示词"""
        title = paper_data.get("title", "")
        abstract = paper_data.get("abstract", "")
        keywords = paper_data.get("keywords", [])
        authors = paper_data.get("author_names", [])
        journal = paper_data.get("journal", "")
        year = paper_data.get("year", "")
        citation_count = paper_data.get("citation_count", 0)
        
        keywords_str = ", ".join(keywords) if keywords else "无"
        authors_str = ", ".join(authors) if authors else "未知作者"
        
        prompt = f"""
请对以下学术论文进行质量分析，要求：

1. 用中文回答
2. 从学术价值、研究方法、创新性、实用性等维度进行分析
3. 给出1-5分的质量评分（5分最高）
4. 指出论文的优点和不足
5. 提供改进建议

论文信息：
标题：{title}
作者：{authors_str}
期刊：{journal}
年份：{year}
引用次数：{citation_count}
关键词：{keywords_str}

摘要：
{abstract}

请提供专业的质量分析：
"""
        return prompt.strip()

# 创建全局实例
gemini_service = GeminiService()
