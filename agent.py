from langchain_core.tools import tool
from langgraph.graph import StateGraph,MessagesState,START,END
from langgraph.prebuilt import ToolNode,tools_condition
from langchain_core.messages import SystemMessage


from hybrid_rag import graph_r,vector_retriever,llm
from extractor import build_nodetype,build_relattype

@tool
def kg_search(sub_query: str) -> str:
    """当问题被拆解成子问题后，使用此工具，从知识图谱中查询单个子问题需要的实体三元组。
    【重要约束】
    1.每次调用只能问一个简单的单跳关系问题，如问“a的b是什么”。
    2.禁止问多跳嵌套问题，如不能问“a的b的c的d是什么”这种多跳问题。
    【返回】
    三元组的JSON字符串
    """
    return graph_r(sub_query)

@tool
def vector_search(query: str) -> str:
    """当问题涉及【具体描述、定义、背景介绍、原文细节】（如“某项目的建设背景”、“某技术的具体原理”等）时使用此工具，从向量数据库中查询相关文档"""
    docs=vector_retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])

tools=[kg_search,vector_search]

llm_tools=llm.bind_tools(tools)

system_prompt=f"""
你是一个水利领域问答助手，可以使用两个工具
1.kg_search：查知识图谱中的单跳关系（一次只能问一个简单关系问题）
2.vector_search：查文档原文描述内容
----------------
【图谱边界-必读】
在拆解问题、调用 kg_search 之前，你必须先了解图谱里有什么。
图谱中只有以下节点类型和关系类型，超出这个范围的问题图谱无法回答（应改用 vector_search 或直接告知用户）。
节点类型：
{build_nodetype()}
关系类型：
{build_relattype()}
------------
【总体工作流程】
根据上面的schema对用户问题进行分析，判断图谱能否查询到答案：
-若图谱无法查询，则这是【描述类】问题（如“xx是什么”“xx怎么样”）->走描述类问题的统一流程
-若图谱可以查询，则这是【关系类】问题（如“xx的a是什么”，”xx在哪里“）->走关系类问题的统一流程
-若图谱能查询到部分答案，这是复杂问题（既问关系也问描述，如“xx的a是什么样的”）->综合使用关系类问题的统一流程和描述类问题的统一流程

【描述类问题统一流程】
直接调用vector_search工具。

【关系类问题统一流程】
1.根据schema边界，判断用户问题需要几跳关系来决定是否拆分问题
2.若问题只需一跳关系，直接调用kg_search工具。
3.若问题需要多跳关系，先拆分问题为多个单跳子问题，对子问题依次调用kg_search工具。最后将所有子问题的结果合并。

【关系类问题统一流程示例】
问题：管理小浪底的机构还管理了哪些项目
分析：根据问题需要先问小浪底的机构是哪个，再问该机构管理了哪些项目，才能得到答案，一共2跳，需要拆解
拆解：
第1步：调用kg_search工具，问“小浪底的机构是哪个”，得到结果(假设得到“黄河水利委员会”)
第2步：用第1步的结果调用kg_search工具，问“黄河水利委员会管理了哪些项目”，得到项目列表
第3步：综合前面几步结果，回答用户

【重要规则】
- 严禁一次性把多跳问题塞给 kg_search（它只能处理单跳）
- 每次调用工具后，要根据返回结果判断下一步：够了就回答，不够就继续查
- 若某次kg_search查询不到结果，可能是问题并没有拆分彻底，可以检查问题是否完全拆分，也可能是kg_search工具内置llm生成cypher的偶然性造成的，可以重试几次，反复失败则尝试使用vector_search工具对子问题进行查询,若仍失败则放弃。
- 确保查询到的信息确实足够充分回答问题再回答，若用户问题里的某个点无法根据查询到的信息确切回答，则直接声明，禁止捏造或假设。
- 回答时，用自然流畅且简短的语言回答
"""

def call_model(state: MessagesState):
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm_tools.invoke(messages)
    return {"messages": [response]}


graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(tools))

graph.add_edge(START, "agent")
graph.add_conditional_edges(
    "agent",
    tools_condition,
)
graph.add_edge("tools", "agent")

agent = graph.compile()


def ask_agent_with_context(messages):
    result=agent.invoke({
        "messages":messages
    })
    final_message=result["messages"][-1]
    return final_message.content,result["messages"]


def ask_agent(question:str)->str:
    answer,_=ask_agent_with_context([
        {"role":"user","content":question}
    ])
    return answer



if __name__ == "__main__":
    answer = ask_agent("长江上的项目的负责机构还负责哪些项目")
    print(answer)
