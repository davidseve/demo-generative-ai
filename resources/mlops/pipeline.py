from kfp import dsl, compiler
from kfp.dsl import InputPath, OutputPath
import os

@dsl.component(
    base_image="python:3.10-slim",
    packages_to_install=[
        "langchain",
        "langchain-community",
        "elasticsearch",
        "transformers",
    ],
)
def ingest_content(pdf_dir: str, urls: list, output_path: OutputPath()):
    import os, json
    from langchain.document_loaders import PyPDFLoader, WebBaseLoader

    docs = []
    if pdf_dir and os.path.isdir(pdf_dir):
        for file in os.listdir(pdf_dir):
            if file.endswith(".pdf"):
                loader = PyPDFLoader(os.path.join(pdf_dir, file))
                docs.extend(loader.load())

    if urls:
        loader = WebBaseLoader(urls)
        docs.extend(loader.load())

    os.makedirs(output_path, exist_ok=True)
    with open(os.path.join(output_path, "docs.json"), "w") as f:
        json.dump([doc.dict() for doc in docs], f)

@dsl.component(base_image="python:3.10-slim", packages_to_install=["langchain"])
def split_chunk(input_path: InputPath(), output_path: OutputPath()):
    import json, os
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document

    with open(os.path.join(input_path, "docs.json")) as f:
        raw_docs = json.load(f)

    docs = [Document(**d) for d in raw_docs]
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    split_docs = splitter.split_documents(docs)

    os.makedirs(output_path, exist_ok=True)
    with open(os.path.join(output_path, "chunks.json"), "w") as f:
        json.dump([d.dict() for d in split_docs], f)

@dsl.component(base_image="python:3.10-slim", packages_to_install=["langchain", "elasticsearch", "transformers", "torch"])
def embed_and_index(input_path: InputPath(), es_url: str, es_pass: str, index_name: str = "rhoai-docs"):
    import json, os
    from elasticsearch import Elasticsearch
    from langchain.vectorstores import ElasticsearchStore
    from langchain.embeddings.huggingface import HuggingFaceEmbeddings
    from langchain.schema import Document

    with open(os.path.join(input_path, "chunks.json")) as f:
        chunks = [Document(**d) for d in json.load(f)]

    es = Elasticsearch(
        es_url,
        basic_auth=("elastic", es_pass),
        verify_certs=False
    )

    embeddings = HuggingFaceEmbeddings()
    ElasticsearchStore.from_documents(chunks, embeddings, es_connection=es, index_name=index_name)

@dsl.pipeline(name="langchain-vector-index-pipeline")
def vector_index_pipeline(
    pdf_dir: str,
    urls: list,
    es_url: str,
    es_pass: str
):
    ingest_task = ingest_content(pdf_dir=pdf_dir, urls=urls)
    split_task = split_chunk(input_path=ingest_task.outputs["output_path"])
    embed_task = embed_and_index(input_path=split_task.outputs["output_path"], es_url=es_url, es_pass=es_pass)

# ---------- BUILD STEP ----------
if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=vector_index_pipeline,
        package_path="vector_index_pipeline.yaml"
    )
