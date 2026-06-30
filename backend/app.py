from flask import Flask, jsonify, request
from flask_cors import CORS
from uuid import uuid4#


from agent import ask_agent_with_context, ask_agent
from knowledgebuild import knowledge_build



app = Flask(__name__)
CORS(app)


@app.route("/")
def home():
    return jsonify({
        "message": "Flask API 已启动"
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "error": "问题不能为空"
        }), 400

    try:
        answer = ask_agent(question)

        return jsonify({
            "question": question,
            "answer": answer
        })

    except Exception as e:
        return jsonify({
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
