import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_groq import ChatGroq
from config.db import chunk_collection
from .prompt import chat_prompt, quiz_prompt

# environment
load_dotenv(dotenv_path = Path(__file__).parent.parent / ".env")

OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY=os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME=os.getenv("PINECONE_INDEX_NAME","teaching-agent")
GROQ_API_KEY=os.getenv("GROQ_API_KEY")

if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"]=OPENAI_API_KEY

#  1. initialize pinecone client
pc=Pinecone(api_key=PINECONE_API_KEY)
index=pc.Index(PINECONE_INDEX_NAME)

#  2. define embedding model
embed_model = OpenAIEmbeddings(model="text-embedding-3-large")

# . llm model
llm=ChatGroq(temperature=0.3, model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY)

# 4. define rag chain
chat_chain=chat_prompt | llm
quiz_chain=quiz_prompt | llm

#  5. define the chat function
async def answer_query(query:str,user_role:str,user_grade:int)->dict:
    embedding=await asyncio.to_thread(embed_model.embed_query,query)

    results=await asyncio.to_thread(
        index.query,vector=embedding,top_k=5,include_metadata=True,filter={
            "grade":user_grade,
            "role":{"$in":["Public",user_role]}
        },
    )
 
    if not results.get("matches"):
        return {"answer":"No relevant information found","sources":[]}

    chunk_ids=[ m["id"] for m in results["matches"]]
    docs=list(chunk_collection.find({"chunk_id":{"$in":chunk_ids}}))
    if not docs:
        return {"answer":"Context unavailable","sources":[]}
    
    doc_map={ d["chunk_id"]:d for d in docs}
    ordered_map=[doc_map[cid] for cid in chunk_ids if cid in doc_map]

    context="\n\n".join(d["text"] for d in ordered_map)
    sources=list({ d["source"] for d in ordered_map})
    
    response= await asyncio.to_thread(
        chat_chain.invoke,
        {"question":query,"context":context}
    )
 
    answer_text=(
        response.content
        if hasattr(response,"content")
        else str(response)
    )

    return {
        "answer":answer_text,
        "sources":sources,
    }


async def quiz_generate(topic:str, user_role:str, user_grade:int, num_questions:int=3) -> dict:
    embedding = await asyncio.to_thread(embed_model.embed_query, topic)

    # retrive relevant embedding from vector db
    results = await asyncio.to_thread(
        index.query, vector=embedding, top_k=5, include_metadata=True, filter={
            "grade": user_grade,
            "role": {"$in": ["Public", user_role]}
        },
    )

    if not results.get("matches"):
        return {"quiz": "No relevant content found to generate quiz", "sources": []}

    chunk_ids = [m["id"] for m in results["matches"]]
    docs = list(chunk_collection.find({"chunk_id": {"$in": chunk_ids}}))
    if not docs:
        return {"quiz": "Context unavailable", "sources": []}

    doc_map = {d["chunk_id"]: d for d in docs}
    ordered_map = [doc_map[cid] for cid in chunk_ids if cid in doc_map]

    context = "\n\n".join(d["text"] for d in ordered_map)
    sources = list({d["source"] for d in ordered_map})

    response = await asyncio.to_thread(
        quiz_chain.invoke,
        {"context": context, "num_questions": num_questions}
    )

    quiz_text = (
        response.content
        if hasattr(response, "content")
        else str(response)
    )

    return {
        "quiz": quiz_text,
        "sources": sources,
    }




