"""
数据库配置文件
支持直接指定数据库、ID映射和索引文件的完整路径
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

class DatabaseConfig:
    """数据库配置管理类 - 支持直接路径配置"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """加载数据库配置"""

        # 默认配置
        default_config = {
            "database_path": str(self.project_root / "openalex_v1.db"),
            "id_map_path": str(self.project_root / "id_map_v1.json"),
            "index_path": str(self.project_root / "papers_v1.index"),
            "description": "默认配置 - OpenAlex V1"
        }


        
        # 检查配置文件
        config_file = self.project_root / ".database_config"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    
                # 尝试解析为JSON
                try:
                    self._config = json.loads(content)
                    # 验证必要字段
                    required_fields = ["database_path", "id_map_path", "index_path"]
                    for field in required_fields:
                        if field not in self._config:
                            raise ValueError(f"配置文件缺少必要字段: {field}")
                    return
                except json.JSONDecodeError:
                    if content in ["openalex_v1", "openalex_v3"]:
                        self._config = self._get_legacy_config(content)
                        return
                    else:
                        print(f"警告: 配置文件格式错误，使用默认配置")
                        
            except Exception as e:
                print(f"警告: 读取配置文件失败 ({e})，使用默认配置")
        
        # 使用默认配置
        self._config = default_config
    
    def _get_legacy_config(self, db_name: str) -> Dict[str, Any]:
        """处理旧版配置格式的兼容性"""
        legacy_configs = {
            "openalex_v1": {
                "database_path": str(self.project_root / "openalex_v1.db"),
                "id_map_path": str(self.project_root / "id_map_v1.json"),
                "index_path": str(self.project_root / "papers_v1.index"),
                "description": "兼容模式 - OpenAlex V1"
            },
            "openalex_v3": {
                "database_path": str(self.project_root / "openalex_v3.db"),
                "id_map_path": str(self.project_root / "id_map_v3.json"),
                "index_path": str(self.project_root / "papers_v3.index"),
                "description": "兼容模式 - OpenAlex V3"
            }
        }
        return legacy_configs.get(db_name, legacy_configs["openalex_v1"])
    
    def get_database_path(self) -> Path:
        """获取数据库文件路径"""
        return Path(self._config["database_path"])
    
    def get_id_map_path(self) -> Path:
        """获取ID映射文件路径"""
        return Path(self._config["id_map_path"])
    
    def get_index_path(self) -> Path:
        """获取FAISS索引文件路径"""
        return Path(self._config["index_path"])
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取当前配置信息"""
        info = self._config.copy()
        
        # 检查文件是否存在
        db_path = self.get_database_path()
        id_map_path = self.get_id_map_path()
        index_path = self.get_index_path()
        
        info["database_exists"] = db_path.exists()
        info["id_map_exists"] = id_map_path.exists()
        info["index_exists"] = index_path.exists()
        
        if db_path.exists():
            info["database_size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)
        else:
            info["database_size_mb"] = 0
            
        return info
    
    def update_config(self, database_path: str, id_map_path: str, index_path: str, description: str = "") -> bool:
        """更新配置并保存到文件"""
        new_config = {
            "database_path": database_path,
            "id_map_path": id_map_path,
            "index_path": index_path,
            "description": description or "用户自定义配置"
        }
        
        try:
            # 保存到配置文件
            config_file = self.project_root / ".database_config"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            
            # 更新内存中的配置
            self._config = new_config
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def validate_config(self) -> Dict[str, Any]:
        """验证当前配置的有效性"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # 检查数据库文件
        db_path = self.get_database_path()
        if not db_path.exists():
            validation_result["valid"] = False
            validation_result["errors"].append(f"数据库文件不存在: {db_path}")
        
        # 检查ID映射文件
        id_map_path = self.get_id_map_path()
        if not id_map_path.exists():
            validation_result["warnings"].append(f"ID映射文件不存在: {id_map_path} (智能推荐功能将不可用)")
        
        # 检查索引文件
        index_path = self.get_index_path()
        if not index_path.exists():
            validation_result["warnings"].append(f"FAISS索引文件不存在: {index_path} (智能推荐功能将不可用)")
        
        return validation_result


# 全局配置实例
db_config = DatabaseConfig()

def get_database_config() -> Dict[str, Any]:
    """获取数据库配置字典"""
    return db_config._config

