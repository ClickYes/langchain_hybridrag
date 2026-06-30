from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate,ChatPromptTemplate
from operator import itemgetter
from langchain_core.runnables import RunnableLambda
import re

from langchain_neo4j import Neo4jGraph
from dotenv import load_dotenv
load_dotenv()
import json

from schema import NodeTypes_Description, RelationTypes_Description
from extractor import init_vectorstore,init_neo4j,init_embeddings,build_nodetype,build_relattype,ensure_neo4j_indexes


llm=ChatOpenAI(
    model="glm-5.1",
    extra_body={"enable_thinking":False}
    )
vectorstore=init_vectorstore()
neo4j_graph=init_neo4j()

node_labels=list(NodeTypes_Description.keys())
#创建全文索引
def create_index():
    labels="|".join(node_labels)

    cypher=f"""
    CREATE FULLTEXT INDEX fulltext
    IF NOT EXISTS 
    FOR (n:{labels})
    ON EACH [n.name,n.description,n.aliases]
    """
    print("[!] 检查全文索引中")
    neo4j_graph.query(cypher)
    print("[!] 全文索引处理完成")


#create_index()
#创建向量索引
def create_vector_index():
    for label in node_labels:
        index_name=f"{label.lower()}_embedding"
        cypher=f"""
        CREATE VECTOR INDEX {index_name} 
        IF NOT EXISTS
        FOR (n:{label})
        ON n.embedding
        OPTIONS {{
            indexConfig:{{
                `vector.dimensions`:768,
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        #print("生成的Cypher：")
        #print(cypher)
        print(f"[!] 检查向量索引中：{index_name}")
        neo4j_graph.query(cypher)
        print(f"[!] 向量索引处理完成：{index_name}")
    
#create_vector_index()







#图全文检索
def node_recall_fulltext(query:str,score:float=0.5,top_k:int=20):
#    cypher=f"""
#    CALL db.index.fulltext.queryNodes('fulltext',$query)
#    YIELD node,score
#    WHERE score>=$score
#    MATCH (node)-[r]->(neighbor)
#    RETURN node.name as source,neighbor.name as target,type(r) as relation_type,node.aliases as source_aliases,neighbor.aliases as target_aliases
#    //LIMIT $top_k

#    UNION ALL

#    CALL db.index.fulltext.queryNodes('fulltext',$query)
#    YIELD node,score
#    WHERE score>=$score
#    MATCH (neighbor)-[r]->(node)
#    RETURN neighbor.name as source,node.name as target,type(r) as relation_type,neighbor.aliases as source_aliases,node.aliases as target_aliases    
   
#    LIMIT $top_k
#    """
    cypher=f"""
    CALL db.index.fulltext.queryNodes('fulltext',$query)
    YIELD node,score
    WHERE score>=$score
    RETURN node.name as name,node.aliases as aliases,labels(node)[0] as type,score
    LIMIT $top_k
    """
    params={
    "query":query,
    "score":score,
    "top_k":top_k
   }
    results= neo4j_graph.query(cypher,params=params)
    results.sort(key=lambda x:x["score"],reverse=True)
    nodes=[]
    for i,result in enumerate(results,1):
        name=result["name"]
        aliases = "、".join(filter(None, result['aliases'] or [])) or "暂无"#过滤掉空字符串
        #type=result["type"]
        score=round(result["score"],4)
        nodes.append(f"{i}. {name}(别名：{aliases}){score}")
#    for result in results:
#       source=result["source"]
#       relation_type=result["relation_type"]
#       source_aliases=result.get("source_aliases","")
#       target_aliases=result.get("target_aliases","")
    
#       relation_desc=RelationTypes_Description.get(relation_type,relation_type)
#       triplets.append(f"{source}(别名：{source_aliases}) → {relation_desc} → {target}(别名：{target_aliases})")
#    if not triplets:
#         return ""
    return "\n".join(nodes) + "\n"
#向量检索
vector_retriever=vectorstore.as_retriever(search_kwargs={"k":5})

embeddings=init_embeddings()
#向量召回候选节点
def node_recall_vector(query:str,score:float=0.8,top_k:int=8):

    query_embedding=embeddings.embed_query(query)
    candidates=[]
    for label in node_labels:
        index_name=f"{label.lower()}_embedding"
        cypher=f"""
        CALL db.index.vector.queryNodes(
        $index_name,
        $top_k,
        $query_embedding
        )
        YIELD node,score
        WHERE score>=$score
        RETURN node.name as name,node.aliases as aliases,labels(node)[0] as type,score
        """
        params={
            "index_name":index_name,
            "top_k":top_k,
            "query_embedding":query_embedding,
            "score":score
        }
        results=neo4j_graph.query(cypher,params=params)
        for result in results:
            candidates.append({
                "name":result["name"],
                "aliases":result["aliases"],
                "type":result["type"],
                "score":round(result["score"],4)
                })
    candidates.sort(key=lambda x:x["score"],reverse=True)
    candidates=candidates[:top_k]
    return candidates   

def graph_cypher(query):
    candidates=node_recall_vector(query)
    candidates_str=[]
    for i,n in enumerate(candidates,1):
        aliases = "、".join(filter(None, n['aliases'] or [])) or "暂无"#过滤掉空字符串
        candidates_str.append(f"{i}.{n['name']}（别名：{aliases}）")#，节点类型：{n['type']}
    candidates_text="\n".join(candidates_str)
    full_text=node_recall_fulltext(query)
    
    prompt=f"""
        你是一个简单问题的Cypher查询语句生成器，根据简单问题生成对应的单跳Cypher查询语句。
        【重要约束】
        1.生成的Cypher语句会直接被送往查询器查询，禁止有任何语法错误，绝对禁止用任何代码块字符包裹，必须输出干净可运行的Cypher语句。
        2.生成的Cypher语句要参考图谱的schema边界，禁止生成与图谱schema无关的查询语句。
        3.生成的Cypher语句要根据图谱schema边界的说明判断关系的方向，严禁生成颠倒关系头尾的查询语句。
        4.生成的Cypher语句必须是单跳查询，禁止生成多跳查询。
        5.生成的Cypher语句的RETURN的返回内容为：关系类型、头节点名、头节点别名、尾节点名、尾节点别名。
        【示例】
        问题：小浪底位于哪里？
        分析：
            schema中显示有”位于某地“关系与问题匹配，”位于某地”在边界说明中以地点为尾节点，
            所以关系方向为”小浪底“ - “位于某地” -> “地点” 
        生成的Cypher语句为：
            MATCH (p)-[r:LOCATED_IN]->(l:Location)
            WHERE p.name="小浪底"
            RETURN p.name as r1_source, p.aliases as r1_source_aliases, 
            type(r) as r1_type, l.name as r1_target, l.aliases as r1_target_aliases
        -------------------
        用户问题：
        {query}
        -------------------
        图谱schema的节点类型边界：
        {build_nodetype()}
        -------------
        图谱schema的关系类型边界：
        {build_relattype()}
        -------------
        节点向量检索返回的候选节点：
        {candidates_text}
        ---------------
        节点全文检索返回的候选节点：
        {full_text}
        ---------------
        【自查】生成Cypher后，必须按以下清单逐项自查，有问题立即修正：
        1.关系类型与首尾节点的节点类型是否与图谱schema的边界匹配？
        2.关系方向和问题的语义方向是否颠倒？
        3.生成的内容是否存在语法错误，是否确实是干净合法的Cypher查询语句，会不会与其他数据库查询语句混淆？会不会报错,会不会丢失字段？
        4.生成的Cypher语句是否是一个单跳查询？
        -------------------
        """
    cypher_prompt=ChatPromptTemplate.from_messages([
        ("system",prompt),
        ("human","用户问题：\n{query}"),
        ])
    chain=cypher_prompt|llm|StrOutputParser()

    cypher=chain.invoke({"query":query})
    #print(f"[DEBUG] 生成的Cypher查询语句：{cypher}")
    return cypher
print("[INFO] 测试Cypher查询语句生成...")
# print(graph_cypher("长江上项目的负责机构还有哪些项目"))

def fix_cypher(cypher):
    cypher = re.sub(r'^\s*```(?:cypher)?\s*', '', cypher, flags=re.IGNORECASE)
    cypher = re.sub(r'\s*```\s*$', '', cypher)
    cypher = cypher.strip()

    cypher=re.sub(
        r'([a-zA-Z_]\w*)\.type\b',
        r'type(\1)',
        cypher,
    )
    return cypher

def graph_r(query):
    ensure_neo4j_indexes(neo4j_graph)
    cypher=fix_cypher(graph_cypher(query))
    print(f"[DEBUG] 修正后的Cypher查询语句：\n{cypher}")
    try:
        results=neo4j_graph.query(cypher)
        print(f"[DEBUG] 图谱查询结果数量：{len(results)}")
        print(f"[DEBUG] 结果：{results}")
    except Exception as e:
        print(f"知识图谱检索失败：{e}")
        return "暂无"
    kg_context=json.dumps(results,ensure_ascii=False,indent=2) if results else "暂无"
    return kg_context


        













#问答提示词模板
prompt_template=PromptTemplate.from_template(
"""
你是一个严谨的RAG助手。
请根据已有信息自然地回答问题，如果已有信息无法回答问题请直接声明。
回答时尽量不要加上”根据信息“这类冗余词汇。
回答里第一次提及的对象需要具体指定，不能用指示代词。
确保回答内容与问题自然连贯。
------------
在回答后输出使用了已有信息中的哪些内容，包括知识图谱检索信息的相关三元组，以及向量检索到的文本中的文件名（不要翻译）和相关内容，尽量一行行输出，每个三元组占一行，每个文本占一行。若未使用到已有信息则不必返回。
【格式说明】：
使用了已有信息中的以下部分：
知识图谱检索：
-源节点（别名：源节点别名） → 关系类型 → 目标节点（别名：目标节点别名）
-...
【注意：如节点不存在别名可以不写，关系类型=！必须！=根据schema中的关系类型说明转为中文，绝对禁止输出英文关系类型】
向量检索：
-【文件名】相关内容句段
------------
schema关系类型说明：
{relattype}
-----------
知识图谱检索的已有信息：
{kg_context}
----------
向量检索的已有信息：
{vector_context}
----------
问题：
{query}
"""
)

#初始化RAG链
def init_rag_chain():
    rag_chain=(
        {"query": RunnablePassthrough()}
        | RunnablePassthrough.assign(relattype=lambda _: build_relattype(),
            kg_context=itemgetter("query") | RunnableLambda(graph_r),#包装成可调用对象
            vector_context=itemgetter("query") | vector_retriever
        )
        | prompt_template
        | llm
        | StrOutputParser()
    )
    return rag_chain
