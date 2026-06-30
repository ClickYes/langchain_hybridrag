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
import re
import unicodedata

def normalize_name(name: str) -> str:
    """节点名归一化：用于去重前的预处理"""
    if not name:
        return name
    # 1. 全角转半角（如全角空格→半角空格，全角括号→半角括号）
    name = unicodedata.normalize("NFKC", name)
    # 2. 去掉首尾空白
    name = name.strip()
    # 3. 合并多个空格为一个
    name = re.sub(r'\s+', ' ', name)
    # 4. 统一中英文括号
    name = name.replace('（', '(').replace('）', ')')
    return name


def normalize_aliases(aliases, main_name=None):
    """别名列表归一化：去空、去重、去掉与主名相同的别名。"""
    clean_aliases = []
    seen = set()
    main_name = normalize_name(main_name) if main_name else None

    for alias in aliases or []:
        alias = normalize_name(alias)
        if not alias:
            continue
        if main_name and alias == main_name:
            continue
        if alias in seen:
            continue
        clean_aliases.append(alias)
        seen.add(alias)

    return clean_aliases


#向量数据库
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




#图数据库

def init_neo4j()->Neo4jGraph:
    return Neo4jGraph()

_indexes_ready = False

def ensure_neo4j_indexes(neo4j_graph: Neo4jGraph):
    """懒加载创建 Neo4j 索引。
    第一次需要用索引时创建，后面再调用会直接跳过。
    """
    global _indexes_ready
    if _indexes_ready:
        return

    print("[!] 检查 Neo4j 索引...")

    # 1. 创建全文索引
    labels = "|".join(NodeTypes_Description.keys())
    fulltext_cypher = f"""
    CREATE FULLTEXT INDEX fulltext
    IF NOT EXISTS
    FOR (n:{labels})
    ON EACH [n.name, n.description, n.aliases]
    """
    neo4j_graph.query(fulltext_cypher)

    # 2. 为每个节点类型创建向量索引
    for node_type in NodeTypes_Description.keys():
        index_name = f"{node_type.lower()}_embedding"
        vector_cypher = f"""
        CREATE VECTOR INDEX {index_name}
        IF NOT EXISTS
        FOR (n:{node_type})
        ON n.embedding
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: 768,
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        neo4j_graph.query(vector_cypher)
    neo4j_graph.query("CALL db.awaitIndexes(300)")#等待索引创建完成
    _indexes_ready = True
    print("[!] Neo4j 索引检查完成")


#提取三元组
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


#抽取三元组提示词
SYSTEM_PROMPT=f"""
你是一个水利知识图谱抽取助手，你的任务是从文本中抽取符合schema设计的节点和关系。
【重要规则】
-关系和节点的type字段必须从schema允许的类型中选择。
-实体名要归一化，去除冗余修饰，同一实体使用同一名称。
-不要编造文本中未出现的内容。
-实体和关系抽取必须完整，符合schema的都应该积极抽取。
-复合命名实体里的包含实体也应被抽取出来（如“甘肃水库”必须抽出“甘肃”作为Location，并建立关系“甘肃水库 -> LOCATED_IN -> 甘肃”，禁止出现抽取“甘肃水库”但未抽取“甘肃”的情况）。
-若某段文本内容与schema设计和水利知识无关，不必返回节点和关系。
-强烈建议为每个节点和关系添加description字段,但不能编造文本中未出现的内容。

【类型判别要点】
判断类型时先对照schema信息，判断实体本质上属于什么类型，严格按照schema说明仔细对应。
节点类型与边界：
{build_nodetype()}
----------------
关系类型与边界：
{build_relattype()}
"""

def build_llm():
    return ChatOpenAI(
        temperature=0,
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


#建立节点向量嵌入图
def node_to_embedding(node):
    #type_str=NodeTypes_Description.get(node.type)
    #desc=node.description or ""
    aliases=[a for a in (node.aliases or []) if a]
    if aliases:
        aliases_text="、 ".join(aliases)
        text=(
            f"{node.name}，别名又叫{aliases_text}"#，{desc}"
        )
    else:
        text=(
            f"{node.name}"#，{desc}"
        )

    embedding=init_embeddings().embed_query(text)
    return embedding


def write_node(node, neo4j_graph):
    """写入节点并智能合并：保留长描述，累加别名。"""
    embedding = node_to_embedding(node)
    cypher = f"""
    MERGE (n:{node.type} {{name:$name}})
    ON CREATE SET 
        n.description = $description,
        n.aliases = coalesce($aliases, []),
        n.embedding = $embedding
    ON MATCH SET 
        n.description = CASE 
            WHEN size(coalesce($description, '')) > size(coalesce(n.description, ''))
            THEN $description ELSE n.description END,
        n.aliases = apoc.coll.toSet(coalesce(n.aliases, []) + coalesce($aliases, [])),
        n.embedding = $embedding
    """
    neo4j_graph.query(cypher, {
        "name": node.name, "description": node.description,
        "aliases": node.aliases or [], "embedding": embedding,
    })


def find_similar(node, neo4j_graph, threshold=0.99):
    """在同类型节点里查阈值以上的最相似节点。返回名字str，没找到返回None。"""
    cypher = f"""
    MATCH (n:{node.type} {{name:$name}})
    CALL db.index.vector.queryNodes($index_name, 2, n.embedding)
    YIELD node AS dup, score
    WHERE score >= $threshold AND dup.name <> $name
    RETURN dup.name AS name LIMIT 1
    """
    result = neo4j_graph.query(cypher, {
        "name": node.name,
        "index_name": f"{node.type.lower()}_embedding",
        "threshold": threshold,
    })
    return result[0]["name"] if result else None

def find_same_entity_by_name_alias(node, neo4j_graph):
    """在同类型节点里按name/aliases精确查重。返回名字str，没找到返回None。"""
    cypher=f"""
    MATCH (dup:{node.type})
    WHERE dup.name <> $name
    AND (
        $name IN coalesce(dup.aliases, [])
        OR dup.name IN $aliases
        OR any(alias IN coalesce(dup.aliases, []) WHERE alias IN $aliases)
    )
    RETURN dup.name AS name LIMIT 1
    """
    result=neo4j_graph.query(cypher,{
        "name":node.name,
        "aliases":node.aliases or [],
    })
    return result[0]["name"] if result else None


def merge_nodes(current_name, keeper_name, node_type, neo4j_graph):
    """把current_name节点合并进keeper_name。返回keeper_name。
    - 描述：取两者中最长的。
    - 别名：keeper 旧别名 + dup 旧别名 + dup 主名，去重
    - 关系：APOC 自动重定向到 keeper（虽然没有关系但是方便迁移）
    """
    # 查两节点的描述和别名
    info_cypher = f"""
    MATCH (k:{node_type} {{name:$keeper}})
    MATCH (d:{node_type} {{name:$current}})
    RETURN k.description AS k_desc, d.description AS d_desc,
           k.aliases AS k_aliases, d.aliases AS d_aliases
    """
    r = neo4j_graph.query(info_cypher, {
        "keeper": keeper_name, "current": current_name
    })[0]
    
    # 挑最长描述
    descs = [d for d in [r["k_desc"], r["d_desc"]] if d]
    best_desc = max(descs, key=len) if descs else None
    
    # 拼接所有别名（双方旧别名 + dup 主名），统一清洗、去重、去掉 keeper 主名
    all_aliases = normalize_aliases(
        (r["k_aliases"] or []) + (r["d_aliases"] or []) + [current_name],
        main_name=keeper_name
    )
    
    # Step 2: APOC 合并
    merge_cypher = f"""
    MATCH (keeper:{node_type} {{name:$keeper}})
    MATCH (dup:{node_type} {{name:$current}})
    CALL apoc.refactor.mergeNodes([keeper, dup], {{ 
        properties: 'discard',
        mergeRels: true
    }}) YIELD node AS merged
    SET merged.aliases = $all_aliases,
        merged.description = $best_desc
    """
    neo4j_graph.query(merge_cypher, {
        "keeper": keeper_name, "current": current_name,
        "best_desc": best_desc, "all_aliases": all_aliases,
    })
    return keeper_name

def write_rel(rel, neo4j_graph):
    """写入关系。"""
    cypher = f"""
    MATCH (s {{name:$source}})
    MATCH (t {{name:$target}})
    MERGE (s)-[r:{rel.type}]->(t)
    SET r.description = $description
    """
    neo4j_graph.query(cypher, {
        "source": rel.source, "target": rel.target,
        "description": rel.description,
    })



#写入图数据库
def write_kg(graph:Graph,neo4j_graph:Neo4jGraph):
    ensure_neo4j_indexes(neo4j_graph)

    name_map={}#节点名映射表
    for node in graph.nodes:
        node.name=normalize_name(node.name)
        node.aliases=normalize_aliases(node.aliases, main_name=node.name)
        original_name=node.name
        # cypher=f"""
        # MERGE (n:{node.type}{{name:$name}})
        # SET n.description=$description,n.aliases=$aliases,n.embedding=$embedding
        # """
        # params={"name":node.name,"description":node.description,"aliases":node.aliases,"embedding":embedding}       
        # neo4j_graph.query(cypher,params)
        write_node(node,neo4j_graph)
        same=find_same_entity_by_name_alias(node,neo4j_graph)
        if same:
            kept=merge_nodes(node.name,same,node.type,neo4j_graph)
            name_map[original_name]=kept
            print(f"[!] 别名合并节点：{original_name} -> {kept}")
        else:
            name_map[original_name]=node.name
            print(f"[!] 无可合并节点：{original_name}")

    for rel in graph.relationships:
        rel.source=normalize_name(rel.source)
        rel.target=normalize_name(rel.target)
        rel.source=name_map.get(rel.source,rel.source)
        rel.target=name_map.get(rel.target,rel.target)
        # cypher=f"""
        # MATCH (s{{name:$source}})
        # MATCH (t{{name:$target}})

        # MERGE (s)-[r:{rel.type}]->(t)
        # SET r.description=$description
        # """
        # params={"source":rel.source,"target":rel.target,"description":rel.description}
        # neo4j_graph.query(cypher,params)
        write_rel(rel,neo4j_graph)
