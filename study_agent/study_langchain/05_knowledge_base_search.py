from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")


from langchain_chroma import Chroma

vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",  # Where to save data locally, remove if not necessary
)

# results = vector_store.similarity_search(
#     "计算流水线是什么？"
# )
# i = 0
# for doc in results:
#     i = i + 1
#     print(f"第{i}个: ")
#     print(doc)

results = vector_store.similarity_search_with_score("计算流水线是什么？")
doc, score = results[0]

i = 0
for doc, score in results:
    i = i + 1
    print(f"第{i}个, 分数({score}): ")
    print(doc)
