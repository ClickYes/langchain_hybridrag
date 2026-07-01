from flask import Flask, jsonify, request
from flask_cors import CORS

from agent import ask_agent_with_context
from knowledgebuild import knowledge_build
from chat_memory import init_chat_db, get_or_create_session_id, get_messages, save_message



app = Flask(__name__)
CORS(app)
init_chat_db()



@app.route("/")
def home():
    return jsonify({
        "message": "Flask API 已启动"
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    question = data.get("question", "").strip()
    session_id = data.get("session_id", "").strip()

    if not question:
        return jsonify({
            "error": "问题不能为空"
        }), 400

    session_id = get_or_create_session_id(session_id)
    history = get_messages(session_id)
    messages=history+[{"role": "user", "content": question}]
    try:
        answer = ask_agent_with_context(messages)
        save_message(session_id, "user", question)
        save_message(session_id, "assistant", answer)

        return jsonify({
            "session_id": session_id,
            "question": question,
            "answer": answer
        })

    except Exception as e:
        return jsonify({
            "session_id": session_id,
            "question": question,
            "error": "调用 Agent 时出错",
            "detail": str(e)
        }), 500



@app.route("/build-kb", methods=["POST"])
def build_kb():
    try:
        result = knowledge_build()

        return jsonify({
            "message": "知识库构建完成",
            **result
        })

    except Exception as e:
        return jsonify({
            "error": "知识库构建失败",
            "detail": str(e)
        }), 500



if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
