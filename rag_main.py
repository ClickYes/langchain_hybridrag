from hybrid_rag import init_rag_chain
from knowledgebuild import knowledge_build

def rag_main():
    # 循环让用户选择，直到输入正确为止
    while True:
        # 让用户选择功能：构建知识库 还是 启动问答
        choose=input("输入1进入构建知识库流程，输入2进入RAG问答流程：")
        # 去除用户输入可能的空白字符（比如不小心按了空格）
        choose=choose.strip()
        
        if choose=="1":
            # 选项1：构建知识库
            print("[INFO] 进入知识库构建流程...")
            knowledge_build()
            print("[INFO] 知识库构建完成")
        elif choose=="2":
            # 选项2：启动RAG问答
            print("[INFO] 初始化RAG问答链...")
            rag_chain=init_rag_chain()
            while True:
                # 获取用户问题
                question=input("\n请输入你的问题（空输入则退出）：")
                question=question.strip()
                
                # 如果是空输入，跳过
                if not question:
                    break
                
                # 调用RAG链得到回答
                print("\n正在思考...\n")
                answer=rag_chain.invoke(question)
                
                # 打印回答
                print("回答：")
                print(answer)
        else:
            # 输入错误，提示用户重新输入
            print("[!] 输入无效，请重新输入1或2\n")
            continue

if __name__ == "__main__":
    rag_main()
