<script setup lang="ts">
import { ref } from 'vue'

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

const question = ref('')
const loading = ref(false)
// const sessionId = ref(localStorage.getItem('rag_session_id') || '')
const sessionId = ref('')


const buildingKb = ref(false)
const kbStatus = ref<'idle' | 'success' | 'error'>('idle')
const kbMessage = ref('知识库尚未构建。请先构建后再开始问答。')

const messages = ref<ChatMessage[]>([
  {
    role: 'assistant',
    content: '你好，我是水利知识 RAG 助手，请输入你的问题。',
  },
])

async function sendQuestion() {
  const text = question.value.trim()

  if (!text) {
    return
  }

  messages.value.push({
    role: 'user',
    content: text,
  })

  question.value = ''
  loading.value = true

  try {
    const response = await fetch('http://127.0.0.1:5000/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question: text,
        session_id: sessionId.value,
      }),
    })

    const data = await response.json()

    if (data.session_id) {
      sessionId.value = data.session_id
      // localStorage.setItem('rag_session_id', data.session_id)
    }

    messages.value.push({
      role: 'assistant',
      content: data.answer,
    })
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '请求后端失败，请确认 Flask 服务已经启动。',
    })
  } finally {
    loading.value = false
  }
}

async function buildKnowledgeBase() {
  buildingKb.value = true
  kbStatus.value = 'idle'
  kbMessage.value = '知识库正在构建中，请稍等...'

  try {
    const response = await fetch('http://127.0.0.1:5000/build-kb', {
      method: 'POST',
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.error || '知识库构建失败')
    }

    kbStatus.value = 'success'
    kbMessage.value = data.message || '知识库构建完成，现在可以开始提问。'
  } catch (error) {
    kbStatus.value = 'error'
    kbMessage.value = '知识库构建失败，请确认 Flask 后端 /build-kb 接口已经实现。'
  } finally {
    buildingKb.value = false
  }
}

</script>

<template>
  <div class="page">
    <header class="header">
      <h1>水利知识 RAG 助手</h1>
      <p>基于文档检索 + 知识图谱的问答 Demo</p>
    </header>

    <section class="kb-panel" :class="kbStatus">
      <div class="kb-info">
        <h2>知识库构建</h2>
        <p>{{ kbMessage }}</p>
      </div>

      <button
        class="kb-button"
        @click="buildKnowledgeBase"
        :disabled="buildingKb"
      >
        {{ buildingKb ? '构建中' : '构建知识库' }}
      </button>
    </section>


    <main class="chat-panel">
      <div class="messages">
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="message-row"
          :class="message.role"
        >
          <div class="message-bubble">
            {{ message.content }}
          </div>
        </div>

        <div v-if="loading" class="message-row assistant">
          <div class="message-bubble">
            正在思考中...
          </div>
        </div>
      </div>

      <div class="input-area">
        <textarea
          v-model="question"
          placeholder="请输入你的问题，例如：三峡工程位于哪里？"
          rows="3"
        />

        <button @click="sendQuestion" :disabled="loading">
          {{ loading ? '发送中' : '发送' }}
        </button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fb;
  padding: 32px;
  box-sizing: border-box;
  font-family: Arial, 'Microsoft YaHei', sans-serif;
}

.header {
  max-width: 900px;
  margin: 0 auto 24px;
}

.header h1 {
  margin: 20px;
  color: #1f2937;
}

.header p {
  color: #6b7280;
}

.kb-panel {
  max-width: 900px;
  margin: 0 auto 16px;
  padding: 18px 20px;
  background: white;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.kb-info h2 {
  margin: 0 0 8px;
  font-size: 18px;
  color: #1f2937;
}

.kb-info p {
  margin: 0;
  color: #6b7280;
  line-height: 1.6;
}

.kb-panel.success {
  border-color: #86efac;
  background: #f0fdf4;
}

.kb-panel.error {
  border-color: #fca5a5;
  background: #fef2f2;
}

.kb-button {
  width: 120px;
  height: 42px;
  flex-shrink: 0;
}


.chat-panel {
  max-width: 900px;
  height: 720px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message-row.user .message-bubble {
  background: #2563eb;
  color: white;
}

.message-row.assistant .message-bubble {
  background: #f3f4f6;
  color: #111827;
}

.input-area {
  border-top: 1px solid #e5e7eb;
  padding: 16px;
  display: flex;
  gap: 12px;
  background: #fff;
}

textarea {
  flex: 1;
  resize: none;
  padding: 12px;
  font-size: 15px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  outline: none;
}

textarea:focus {
  border-color: #2563eb;
}

button {
  width: 96px;
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: white;
  font-size: 15px;
  cursor: pointer;
}

button:disabled {
  background: #93c5fd;
  cursor: not-allowed;
}
</style>
