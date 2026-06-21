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
from extractor import init_vectorstore,init_neo4j,init_embeddings,build_nodetype,build_relattype


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
vector_retriever=vectorstore.as_retriever(search_kwargs={"k":8})

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
        你是一个Neo4j数据库的查询助手，根据用户的问题、图谱的schema边界和节点检索返回的候选节点，生成对应的Cypher查询语句。
        图谱中仅有边界的节点类型和关系类型，不包含其他的类型
        拿到用户问题后，先将其梳理为查询逻辑链，再根据逻辑链生成Cypher查询语句。
        节点检索返回的是图谱中真实存在的可能与问题匹配的节点，可以作为Cypher查询语句生成的优先参考，但要保证它们真的与问题相关。
        【重要约束】
        一、确保生成的MATCH语句与用户的问题相关，MATCH中一个模式只能有一个三元组，多个模式之间用逗号隔开，通过共享变量连接。
        二、结合图谱的schema边界进行类型判断，绝对禁止混淆节点类型，
        尤其是节点类型里的“地点“和”水系“、”项目”和“技术”等易混淆类型绝对禁止混淆。
        三、你的输出结果会被直接作为Cypher查询语句执行，所以确保你的输出只有干净的Cypher查询语句，不存在其他字符。
        四、不允许编造不在schema中的节点类型或关系类型。
        五、生成的Cypher语句每个关系都要有向，并且严格按照图谱schema里说明的方向，确保起点和终点的类型是正确的，关系都需要有关系变量名，绝对禁止关系括号里不写关系变量名。
        六、结合图谱的schema边界，仔细判断用户问题需要进行多少跳查询，禁止查询无用的信息。
        七、【关键】先梳理清楚回答问题所需的完整逻辑链，再生成Cypher。逻辑链上没有的关系，一律不准出现在MATCH中。任何节点（无论是锚点节点还是中间节点）都禁止额外连接与问题逻辑无关的关系。判断标准：删掉这条关系后，回答问题的核心逻辑链是否仍然完整？如果完整，就是多余的，必须删掉。
        八、禁止使用WITH子句，所有查询都必须在一条MATCH语句中进行。
        九、禁止MATCH后的一个模式中内容超出一个三元组，必须写成多模式，每个模式之间用逗号隔开。
        十、你的输出结果被你的输出结果被输入Cypher查询窗口后，返回的结果会被直接送往llm作为增强信息，RETURN中的字段有且只有查询语句中每个三元组（禁止只返回最后一跳，要让llm看到从【问题实体】到【最终实体】的完整多跳过程）的起点name属性、终点name属性、关系类型、起点aliases属性、终点aliases属性（禁止包含此外的节点属性），字段的命名要让llm能够理解使用。
        -------------------
        【示例】
        用户问题：建在长江上项目的负责机构还有哪些项目？
        逻辑链生成思路：
        用户问题与图谱schema中的节点类型“项目”“河流”“机构”相关，关系类型与“建在某河上”“负责”相关，且“建在某河上”的关系起点是项目，终点是河流，“负责”的关系起点是机构，终点是项目。
        所以逻辑链为：
        项目1-建在某河上->长江，,某机构-负责->项目1，某机构-负责->项目2，三条关系，应返回三组三元组信息，因此MATCH后应有三个模式，三个模式靠共享变量连接。
        根据逻辑链和图谱schema边界，生成Cypher查询语句：
        MATCH (p1:HydraulicProject)-[r1:ON_RIVER]->(w:WaterSystem),
        (o:Organization)-[r2:MANAGES]->(p1),
        (o)-[r3:MANAGES]->(p2:HydraulicProject)
        WHERE w.name="长江"
        RETURN p1.name as r1_source,p1.aliases as r1_source_aliases,type(r1) as r1_type,w.name as r1_target,w.aliases as r1_target_aliases,
        o.name as r2_source,o.aliases as r2_source_aliases,type(r2) as r2_type,p1.name as r2_target,p1.aliases as r2_target_aliases,
        o.name as r3_source,o.aliases as r3_source_aliases,type(r3) as r3_type,p2.name as r3_target,p2.aliases as r3_target_aliases
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
        1.【首要】是否查询了与用户问题所需逻辑链不需要的关系？逐一检查每个三元组：删掉它之后，回答问题的核心逻辑链还完整吗？完整就是多余的，必须删掉。
        2.每个关系的源节点类型和目标节点类型是否与schema一致？
        3.关系方向和问题的语义方向是否颠倒？
        4.关系类型与首尾节点的节点类型是否与图谱schema的边界匹配？
        5.生成的Cypher语句是否足以回答用户问题？跳数是否足够？
        6.仔细思考用户的问题需要几跳才能回答，有没有漏掉中间环节？
        7.生成的Cypher语句是否存在语法错误，是否确实是合法的Cypher查询语句，会不会与其他数据库查询语句混淆？会不会报错,会不会丢失字段？
        -------------------
        【反例：修饰语错位导致的多余关系】
        用户问题：管理小浪底的机构还管理了位于青海省的哪些项目？
        【陷阱分析】问题里有"位于青海省"这个修饰语，但它修饰的是"还管理的项目"（目标项目p2）。不能因为问题里出现了地点修饰语，就给其他节点也顺手连上地点关系。
        逻辑链应为：机构-管理->小浪底，机构-管理->其他项目，其他项目-位于->青海省，共3跳关系。小浪底本身的地点与回答问题无关。
        错误写法（多了一条p1的地点关系）：
        MATCH (o:Organization)-[r1:MANAGES]->(p1:HydraulicProject),
        (p1)-[r2:LOCATED_IN]->(l1:Location),
        (o)-[r3:MANAGES]->(p2:HydraulicProject),
        (p2)-[r4:LOCATED_IN]->(l2:Location)
        WHERE p1.name="小浪底" AND l2.name="青海省"
        错误原因：删掉p1-LOCATED_IN->l1之后，"机构→小浪底，机构→其他项目，其他项目→青海省"的核心逻辑链依然完整，所以这条关系是多余的。
        正确写法：
        MATCH (o:Organization)-[r1:MANAGES]->(p1:HydraulicProject),
        (o)-[r2:MANAGES]->(p2:HydraulicProject),
        (p2)-[r3:LOCATED_IN]->(l:Location)
        WHERE p1.name="小浪底" AND l.name="青海省"
        RETURN o.name as r1_source,o.aliases as r1_source_aliases,type(r1) as r1_type,p1.name as r1_target,p1.aliases as r1_target_aliases,
        o.name as r2_source,o.aliases as r2_source_aliases,type(r2) as r2_type,p2.name as r2_target,p2.aliases as r2_target_aliases,
        p2.name as r3_source,p2.aliases as r3_source_aliases,type(r3) as r3_type,l.name as r3_target,l.aliases as r3_target_aliases
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
    cypher=re.sub(
        r'([a-zA-Z_]\w*)\.type\b',
        r'type(\1)',
        cypher,
    )
    return cypher

def graph_r(query):
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
