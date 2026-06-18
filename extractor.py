from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_neo4j import Neo4jGraph
from sentence_transformers import SentenceTransformer
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv
load_dotenv()

from schema import NodeTypes_Description,RelationTypes_Description,Graph

_embeddings=None

def init_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings=HuggingFaceEmbeddings(
            model_name="./models/sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
            )
    return _embeddings

_vectorstore=None

def init_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore=Chroma(
            embedding_function=init_embeddings(),
            persist_directory="./chroma_db",
            collection_metadata={"hnsw:space": "cosine"}
            )
    return _vectorstore

def extract_to_vectorstore(doc:Document)->None:
    vectorstore=init_vectorstore()
    vectorstore.add_documents([doc])





def init_neo4j()->Neo4jGraph:
    return Neo4jGraph()

def build_nodetype()->str:
    lines=[]
    for typename,desc in NodeTypes_Description.items():
        lines.append(f"-{typename}：{desc}-")
    return "\n".join(lines)

def build_relattype()->str:
    lines=[]
    for reltype,desc in RelationTypes_Description.items():
        lines.append(f"-{reltype}：{desc}-")
    return "\n".join(lines)

SYSTEM_PROMPT=f"""
你是一个水利知识图谱抽取助手，你的任务是从文本中抽取符合schema设计的节点和关系。
抽取时必须严格遵守提供的节点类型及关系类型边界。
关系的type字段必须从允许的关系类型中选择。
节点的type字段必须从允许的节点类型中选择。
实体名要归一化，去除冗余修饰，同一实体使用同一名称。
不要编造文本中未出现的内容。
关系抽取需完整，积极抽取实体之间的关系。
若某段文本内容与schema设计和水利知识无关，不必返回节点和关系。
节点必须与节点类型语义匹配，如：不能把“xx公司”或其他非水利技术实体作为“Technology”节点。
强烈建议为每个节点和关系添加description字段,但不能编造文本中未出现的内容。
节点类型与边界：
{build_nodetype()}
----------------
关系类型与边界：
{build_relattype()}
"""

def build_llm():
    return ChatOpenAI(
        temperature=0.7,
        model="deepseek-v4-flash",
        extra_body={"enable_thinking":False},
        )

def build_extractor():
    llm=build_llm()
    structured_llm=llm.with_structured_output(Graph)
    prompts=ChatPromptTemplate.from_messages([
        ("system",SYSTEM_PROMPT),
        ("human","从该文本中抽取知识图谱：\n{text}"),
        ])
    return prompts|structured_llm

_extractor=None

def extract_kg(text:str)->Graph:
    global _extractor
    if _extractor is None:
        _extractor=build_extractor()
    return _extractor.invoke({"text":text})


def write_kg(graph:Graph,neo4j_graph:Neo4jGraph):
    for node in graph.nodes:
        cypher=f"""
        MERGE (n:{node.type}{{name:$name}})
        SET n.description=$description,n.aliases=$aliases
        """
        params={"name":node.name,"description":node.description,"aliases":node.aliases}
        neo4j_graph.query(cypher,params)
    for rel in graph.relationships:
        cypher=f"""
        MATCH (s{{name:$source}})
        MATCH (t{{name:$target}})

        MERGE (s)-[r:{rel.type}]->(t)
        SET r.description=$description
        """
        params={"source":rel.source,"target":rel.target,"description":rel.description}
        neo4j_graph.query(cypher,params)
