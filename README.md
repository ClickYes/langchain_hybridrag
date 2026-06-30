# Hybrid RAG 混合检索问答系统

基于知识图谱 + 向量检索 + LangGraph Agent 的水利领域问答系统。Vue 前端负责交互，Flask 后端提供接口，Agent 自动选择图谱单跳查询或向量描述检索。

## 环境要求

- Python 3.11（建议用 conda 管理）
- Node.js 18+ 与 npm
- 一个可访问的 Neo4j 数据库
- 一个 OpenAI 兼容的 LLM API（如 DeepSeek、智谱、本地 vLLM 等）

## 后端

### 1. 创建 Python 环境
```bash
conda create -n py311 python=3.11
conda activate py311
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置 `.env`（项目根目录新建）
```
OPENAI_BASE_URL=你的Base URL
OPENAI_API_KEY=你的API Key
NEO4J_URI=你的Neo4j URI
NEO4J_USERNAME=你的Neo4j用户名
NEO4J_PASSWORD=你的Neo4j密码
NEO4J_DATABASE=你的Neo4j数据库名称
```

### 4. 下载嵌入模型（首次运行）
```bash
python fetch_model.py
```
模型从 ModelScope 下载到 `models/`。

### 5. 启动后端
```bash
python backend/app.py
```
默认监听 `http://127.0.0.1:5000`：
- `POST /build-kb` 构建知识库
- `POST /chat` 问答

## 前端

```bash
cd frontend/vue-rag
npm install
npm run dev
```
前端默认请求 `http://127.0.0.1:5000`，需先启动后端。

## 使用

打开前端页面，先点"构建知识库"读取 `knowledge/` 下文档建图，再输入问题问答。

## 项目结构

| 文件 / 目录 | 作用 |
|---|---|
| `backend/app.py` | Flask 后端 API |
| `agent.py` | LangGraph Agent，编排 `kg_search` / `vector_search` |
| `hybrid_rag.py` | RAG 链与检索器 |
| `knowledgebuild.py` | 构建知识库（写入 Neo4j + Chroma） |
| `extractor.py` | 抽取器、Embedding / Neo4j / 向量库初始化 |
| `schema.py` | 图谱 Schema |
| `fetch_model.py` | 从 ModelScope 下载嵌入模型 |
| `knowledge/` | 知识库源文档 |
| `frontend/vue-rag/` | Vue + Vite 前端 |
