# .database_config 配置文件格式说明

## 文件位置
文件应放在项目根目录下，文件名为 `.database_config`（无扩展名）

## 新版配置格式（推荐）
使用JSON格式直接指定所有文件的完整路径：

```json
{
  "database_path": "/path/to/your/database.db",
  "id_map_path": "/path/to/your/id_map.json",
  "index_path": "/path/to/your/papers.index",
  "description": "我的自定义配置"
}
```

### 字段说明
- **database_path**: 数据库文件的完整路径
- **id_map_path**: ID映射文件的完整路径  
- **index_path**: FAISS索引文件的完整路径
- **description**: 配置描述（可选）

### 路径类型支持
- **绝对路径**: `/home/user/data/openalex_v3.db`
- **相对路径**: `./data/openalex_v3.db`
- **Windows路径**: `C:\data\openalex_v3.db`

## 配置示例

### 示例1: 使用绝对路径
```json
{
  "database_path": "/home/user/research/openalex_v3.db",
  "id_map_path": "/home/user/research/id_map_v3.json",
  "index_path": "/home/user/research/papers_v3.index",
  "description": "研究用数据库v3"
}
```

### 示例2: 使用相对路径
```json
{
  "database_path": "./databases/openalex_v1.db",
  "id_map_path": "./vectors/id_map_v1.json", 
  "index_path": "./vectors/papers_v1.index",
  "description": "本地测试数据库"
}
```

### 示例3: Windows路径
```json
{
  "database_path": "D:\\research\\databases\\openalex_v3.db",
  "id_map_path": "D:\\research\\vectors\\id_map_v3.json",
  "index_path": "D:\\research\\vectors\\papers_v3.index",
  "description": "Windows环境配置"
}
```

## 旧版配置格式（兼容性）
系统仍支持旧版单行配置格式，但不推荐使用：

```
openalex_v3
```

此格式会自动转换为新格式，使用项目根目录下的默认文件名。

## 配置文件管理

### 通过代码更新配置
```python
from backend.app.db.config import db_config

# 更新配置
success = db_config.update_config(
    database_path="/path/to/database.db",
    id_map_path="/path/to/id_map.json", 
    index_path="/path/to/papers.index",
    description="新配置"
)
```

### 验证配置
```python
# 验证当前配置
validation = db_config.validate_config()
if not validation["valid"]:
    print("配置错误:", validation["errors"])
if validation["warnings"]:
    print("配置警告:", validation["warnings"])
```

### 获取配置信息
```python
# 获取当前配置详细信息
info = db_config.get_config_info()
print(f"数据库: {info['database_path']}")
print(f"文件是否存在: {info['database_exists']}")
```

## 注意事项

1. **文件路径**: 支持绝对路径和相对路径，相对路径基于项目根目录
2. **文件存在性**: 系统会检查文件是否存在，不存在的文件会产生警告
3. **智能推荐**: ID映射文件和索引文件是智能推荐功能必需的
4. **重启服务**: 修改配置后需要重启后端服务
5. **JSON格式**: 配置文件必须是有效的JSON格式
6. **字符编码**: 配置文件使用UTF-8编码

## 默认配置

如果配置文件不存在或格式错误，系统会使用默认配置：

```json
{
  "database_path": "<项目根目录>/openalex_v3.db",
  "id_map_path": "<项目根目录>/id_map_v3.json",
  "index_path": "<项目根目录>/papers_v3.index",
  "description": "默认配置 - OpenAlex V3"
}
```

## 配置验证

可以通过后端API检查当前配置状态：

```bash
# 获取配置信息
curl http://localhost:8000/api/workspace/dashboard

# 检查智能推荐服务状态
curl http://localhost:8000/api/recommendations/stats
```

系统会在启动时验证配置并在日志中显示文件加载状态。
