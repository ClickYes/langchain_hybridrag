from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import PromptTemplate
from operator import itemgetter
from langchain_core.runnables import RunnableLambda

from langchain_neo4j import Neo4jGraph
from dotenv import load_dotenv
load_dotenv()

from schema import NodeTypes_Description, RelationTypes_Description
from extractor import init_vectorstore,init_neo4j

llm=ChatOpenAI(
    model="deepseek-v4-flash",
    extra_body={"enable_thinking":False}
    )
vectorstore=init_vectorstore()
neo4j_graph=init_neo4j()

node_labels=list(NodeTypes_Description.keys())

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


create_index()

def graph_retriever(query:str,score:float=0.5,top_k:int=20):
   cypher=f"""
   CALL db.index.fulltext.queryNodes('fulltext',$query)
   YIELD node,score
   WHERE score>=$score
   MATCH (node)-[r]->(neighbor)
   RETURN node.name as source,neighbor.name as target,type(r) as relation_type,node.aliases as source_aliases,neighbor.aliases as target_aliases
   //LIMIT $top_k

   UNION ALL

   CALL db.index.fulltext.queryNodes('fulltext',$query)
   YIELD node,score
   WHERE score>=$score
   MATCH (neighbor)-[r]->(node)
   RETURN neighbor.name as source,node.name as target,type(r) as relation_type,neighbor.aliases as source_aliases,node.aliases as target_aliases    
   LIMIT $top_k
   """

   params={
    "query":query,
    "score":score,
    "top_k":top_k
   }
   results= neo4j_graph.query(cypher,params=params)

   triplets=[]
   for result in results:
      source=result["source"]
      target=result["target"]
      relation_type=result["relation_type"]
      source_aliases=result.get("source_aliases","")
      target_aliases=result.get("target_aliases","")
    
      relation_desc=RelationTypes_Description.get(relation_type,relation_type)
      triplets.append(f"{source}(别名：{source_aliases}) → {relation_desc} → {target}(别名：{target_aliases})")
   if not triplets:
        return ""
   return "\n".join(triplets) + "\n"

vector_retriever=vectorstore.as_retriever(search_kwargs={"k":5})

prompt_template=PromptTemplate.from_template(
"""
你是一个严谨的RAG助手。
请根据已有信息自然地回答问题，如果已有信息无法回答问题请直接声明。
回答时尽量不要加上”根据信息“这类冗余词汇。
回答里第一次提及的对象需要具体指定，不能用指示代词。
确保回答内容与问题自然连贯。
------------
在回答后输出使用了已有信息中的哪些内容，包括知识图谱检索信息的相关三元组，以及向量检索到的文本中的文件名（不要翻译）和相关内容，尽量一行行输出，每个三元组占一行，每个文本占一行。
格式：
使用了以下已有信息：
知识图谱检索：
-源节点（别名：源节点别名） → 关系 → 目标节点（别名：目标节点别名）
-...
向量检索：
-【文件名】相关内容句段
------------
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
def init_rag_chain():
    rag_chain=(
        {"query": RunnablePassthrough()}
        | RunnablePassthrough.assign(
            kg_context=itemgetter("query") | RunnableLambda(graph_retriever),#包装成可调用对象
            vector_context=itemgetter("query") | vector_retriever
        )
        | prompt_template
        | llm
        | StrOutputParser()
    )
    return rag_chain