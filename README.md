# Hybrid RAG 混合检索问答系统

知识图谱+向量检索+LangGraph Agent的水利领域问答系统。Vue前端，Flask后端，SQLite存多轮会话。

## 环境要求

- Python 3.11（conda）
- Node.js 18+
- Neo4j，须启用APOC插件
- OpenAI兼容的LLM API

## 目录结构

```
lianxi/
├── backend/
│   ├── app.py              Flask入口
│   ├── agent.py            LangGraph Agent
│   ├── hybrid_rag.py       RAG链
│   ├── knowledgebuild.py   知识库构建
│   ├── extractor.py        抽取与初始化
│   ├── schema.py           图谱Schema
│   ├── chat_memory.py      会话记忆
│   ├── fetch_model.py      下载嵌入模型
│   ├── knowledge/
│   ├── requirements.txt
│   └── .env
└── frontend/vue-rag/
```

## 后端

### 1. 启动Neo4j
```bash
neo4j console
```

### 2. Python环境
```bash
conda create -n py311 python=3.11
conda activate py311
```

### 3. 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

### 4. 在backend/下新建`.env`
```
OPENAI_BASE_URL=
OPENAI_API_KEY=
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=
```
填入对应信息

### 5. 下载嵌入模型
```bash
python fetch_model.py
```

### 6. 启动
```bash
python app.py
```

## 前端
```bash
cd frontend/vue-rag
npm install
npm run dev
```

## 使用

先点"构建知识库"读取`backend/knowledge/`建库，然后问答。
