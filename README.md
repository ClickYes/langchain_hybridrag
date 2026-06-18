# Hybrid RAG 混合检索问答系统

结合知识图谱检索 + 向量检索的RAG问答系统。

## 快速开始

```bash
# 1. 创建并激活环境
conda create -n py311 python=3.11
conda activate py311

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
OPENAI_BASE_URL=你的Base URL
OPENAI_API_KEY=你的API Key
NEO4J_URI=你的Neo4j URI
NEO4J_USERNAME= 你的Neo4j用户名
NEO4J_PASSWORD=你的Neo4j密码
NEO4J_DATABASE=你的Neo4j数据库名称
# 编辑 .env 填写 NEO4J 和 OPENAI API 配置

# 4. 下载嵌入模型
python fetch_model.py

# 5. 运行
python rag_main.py
```

## 使用

运行后按提示选择：
- 输入 `1` → 构建知识库
- 输入 `2` → 开始问答

## 项目文件

| 文件 | 作用 |
|------|------|
| `rag_main.py` | 主入口 |
| `hybrid_rag.py` | RAG链定义 |
| `knowledgebuild.py` | 构建知识库 |
| `schema.py` | 知识图谱schema |
| `extractor.py` | 抽取器初始化 |
| `fetch_model.py` | 下载模型 |
| `knowledge/` | 知识库文档 |
