# PDF -> CHUNKING 
#     ->MONGODB(FULL TEXT STORAGE) 
#     -> PINECONE (EMBEDDING+METADATA)

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.db import chunk_collection

load_dotenv(dotenv_path= Path(__file__).parent.parent / ".env")

OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY=os.getenv("PINECONE_API_KEY")
PINECONE_ENV=os.getenv("PINECONE_ENV","us-east-1")
PINECONE_INDEX_NAME=os.getenv("PINECONE_INDEX_NAME","teaching-agent")

if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"]=OPENAI_API_KEY


UPLOAD_DIR=str(Path(__file__).parent.parent / "upload_docs")
os.makedirs(UPLOAD_DIR,exist_ok=True)

## pinecone global upsert fucntion

pc=None
index=None

def get_pinecone_index():
    global pc,index
    if index is None:
        pc=Pinecone(api_key=PINECONE_API_KEY)
        index=pc.Index(PINECONE_INDEX_NAME)
    return index



async def load_vectorstore(uploaded_files, role: str, doc_id: str, grade: int):
    ## initilize emedding model
    embed_model = OpenAIEmbeddings(model="text-embedding-3-large")
    
    ## get pinecone index
    pinecone_index=get_pinecone_index()
    ## loop through uploaded files
    for file in uploaded_files:
        ## 1. save raw file
        save_path=Path(UPLOAD_DIR) / file.filename
        contents = await file.read()
        with open(save_path,"wb") as f:
            f.write(contents)
        ## 2. load pdf text
        loader=PyPDFLoader(str(save_path))
        documents=loader.load()
        ## 3. chunk text 
        splitter=RecursiveCharacterTextSplitter(chunk_size=500,chunk_overlap=50)
        chunks=splitter.split_documents(documents)
        ## 4. guard condition
        if not chunks:
            print(f"No text extracted from {file.filename}, skipping...")
            continue
        ## 5. dual storing
        ## 5.1 store full text in mongodb
        chunk_docs=[]
        for i,chunk in enumerate(chunks):
            chunk_docs.append({
                "chunk_id":f"{doc_id}-{i}",
                "doc_id":doc_id,
                "text":chunk.page_content,
                "page":int(chunk.metadata.get("page",0)),
                "source":file.filename,
                "grade":grade,
                "role":role,
            })
        if chunk_docs:
            chunk_collection.insert_many(chunk_docs)
        ## 5.2 create embeddings
        texts=[chunk.page_content for chunk in chunks]
        embeddings= await asyncio.to_thread(embed_model.embed_documents,texts)
        # upsert pinecone
        ids=[f"{doc_id}-{i}" for i in range(len(embeddings))]

        metadatas=[
            {
                "doc_id":doc_id,
                "page":int(chunks[i].metadata.get("page",0)),
                "source":file.filename,
                "grade":grade,
                "role":role,
            }
            for i in range(len(embeddings))
        ]

        vectors = [
            {"id": ids[i], "values": embeddings[i], "metadata": metadatas[i]}
            for i in range(len(embeddings))
        ]
        # upsert in batches of 100 (pinecone limit)
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            pinecone_index.upsert(vectors=vectors[i:i+batch_size])

    print(f"Successfully indexed {file.filename}")
