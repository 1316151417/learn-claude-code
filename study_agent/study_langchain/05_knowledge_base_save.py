# 读取文档
from langchain_community.document_loaders import PyPDFLoader
file_path = "/Users/zhoujie/IdeaProjects/learn-claude-code/study_agent/study_langchain/doc/深入理解计算机系统（原书第3版） (Randal E.Bryant David OHallaron) .pdf"
loader = PyPDFLoader(file_path)
docs = loader.load()
print(len(docs))

# 按行拆
from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, chunk_overlap=200, add_start_index=True
)
all_splits = text_splitter.split_documents(docs)
print(len(all_splits))

# 向量化
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

vector_1 = embeddings.embed_query(all_splits[0].page_content)
vector_2 = embeddings.embed_query(all_splits[1].page_content)

assert len(vector_1) == len(vector_2)
print(f"Generated vectors of length {len(vector_1)}\n")
print(vector_1[:10])

# 向量存储
# from langchain_core.vectorstores import InMemoryVectorStore

# vector_store = InMemoryVectorStore(embeddings)
from langchain_chroma import Chroma

vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",  # Where to save data locally, remove if not necessary
)

ids = vector_store.add_documents(documents=all_splits)
print(f"ids: {len(ids)}")