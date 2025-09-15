"""
共享模型管理器
避免重复加载BERT模型，提高启动效率
"""
import logging
from typing import Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class ModelManager:
    """共享模型管理器"""
    
    _instance = None
    _model = None
    _model_name = "all-MiniLM-L6-v2"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_model(self) -> Optional[SentenceTransformer]:
        """获取BERT模型，如果未加载则加载"""
        if self._model is None:
            try:
                logger.info(f"[ModelManager] 正在加载BERT模型: {self._model_name}")
                self._model = SentenceTransformer(self._model_name)
                logger.info(f"[ModelManager] BERT模型加载完成: {self._model_name}")
            except Exception as e:
                logger.error(f"[ModelManager] BERT模型加载失败: {e}")
                return None
        return self._model
    
    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self._model is not None
    
    def unload_model(self):
        """卸载模型（用于测试或内存管理）"""
        self._model = None
        logger.info("[ModelManager] BERT模型已卸载")

# 全局模型管理器实例
model_manager = ModelManager()

