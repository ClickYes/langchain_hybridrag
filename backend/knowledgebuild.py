from extractor import extract_kg,init_neo4j,write_kg,extract_to_vectorstore

from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

file_dir=Path("./knowledge")#知识库目录路径
neo4j_graph=init_neo4j()

def load_docs():
    splitter=RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100#滑动窗口分块（块大小，重叠大小）
        )
    loader=DirectoryLoader(
        path=str(file_dir), 
        loader_cls=TextLoader,
        loader_kwargs={"autodetect_encoding":True}
        )
    docs=loader.load()#加载文件
    docs=splitter.split_documents(docs)
    return docs

def knowledge_build():
    docs = load_docs()
    print(f"切分成了{len(docs)}个文档块")

    success_count = 0
    failed_count = 0

    for i, doc in enumerate(docs, 1):
        print(f"---文档块{i}：----")

        try:
            print(f"文档块{i}正在写入向量数据库")
            extract_to_vectorstore(doc)
            print(f"文档块{i}已写入向量数据库")

            print(f"文档块{i}正在抽取图谱")
            kg = extract_kg(doc.page_content)

            print(f"文档块{i}抽取到的节点：{len(kg.nodes)}个")
            for n in kg.nodes:
                print(f"节点：{n}\n")

            print(f"文档块{i}抽取到的关系：{len(kg.relationships)}个")
            for r in kg.relationships:
                print(f"关系：{r}\n")

            write_kg(kg, neo4j_graph)
            print(f"文档块{i}的抽取图谱已写入Neo4j数据库")

            success_count += 1

        except Exception as e:
            failed_count += 1
            print(f"文档块{i}的抽取失败：{e}")
            continue

        print("=" * 50)

    return {
        "total_chunks": len(docs),
        "success_count": success_count,
        "failed_count": failed_count,
    }


if __name__=="__main__":
    knowledge_build()
