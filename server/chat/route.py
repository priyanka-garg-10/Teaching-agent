from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import datetime
import re

from bson import ObjectId
from auth.routes import authenticate
from chat.chat_query import answer_query, quiz_generate
from config.db import chat_history_collection, quiz_collection, quiz_history

router = APIRouter()


class ChatRequest(BaseModel):
    query: str

class QuizRequest(BaseModel):
    topic:str
    num_questions:Optional[int]=3

class QuizAnswerRequest(BaseModel):
    quiz_id:str
    answers:List[str]


@router.post("/chat")
async def chat(req: ChatRequest, user=Depends(authenticate)):

    if user["role"] != "Student":
        raise HTTPException(
            status_code=403,
            detail="Only students can ask questions"
        )

    response = await answer_query(req.query, user["role"], user["grade"])

    chat_history_collection.insert_one({
        "user_id": user["user_id"],
        "timestamp": datetime.datetime.utcnow(),
        "query": req.query,
        "response": response["answer"],
        "sources": response["sources"],
    })

    return response

@router.post("/quiz")
async def quiz(req: QuizRequest, user=Depends(authenticate)):
    if user["role"] != "Student":
        raise HTTPException(
            status_code=403,
            details="Only students can generate quizzes"
        )
    
    response = await quiz_generate(req.topic, user["role"], user["grade"], req.num_questions)

    quiz = {
        "user_id":user["user_id"],
        "timestamp":datetime.datetime.utcnow(),
        "topic":req.topic,
        "quiz_data":response["quiz"],
        "sources":response["sources"]
    }

    result = quiz_collection.insert_one(quiz)

    return {
        "quiz":response["quiz"],
        "sources":response["sources"],
        "quiz_id":str(result.inserted_id)
    }

@router.post("/quiz/check")
async def check_quiz_answers(request:QuizAnswerRequest,user=Depends(authenticate)):
    quiz_doc = quiz_collection.find_one(
        {"_id":ObjectId(request.quiz_id)}
    )

    if not quiz_doc:
        raise HTTPException(404,"Quiz not found")
    
    if quiz_doc["user_id"] != user["user_id"]:
        raise HTTPException(403,"Unauthorized")
    
    correct_answers=[]
    for line in quiz_doc["quiz_data"].split("\n"):
        if line.startswith("Correct Answer:"):
            correct_answers.append(line.split(":")[1].strip()[0])

    if len(request.answers) != len(correct_answers):
        raise HTTPException(400, "Answer count mismatch")
    
    score=0
    results=[]

    for i, ans in enumerate(request.answers):
        is_correct=ans.strip().upper() == correct_answers[i]
        if is_correct:
            score +=1

        results.append({
            "question_number":i+1,
            "user_answer":ans,
            "correct_answer":correct_answers[i],
            "is_correct":is_correct
        })

    quiz_history.insert_one({
        "user_id": user["user_id"],
        "quiz_id": request.quiz_id,
        "timestamp": datetime.datetime.utcnow(),
        "topic": quiz_doc["topic"],
        "score": score,
        "total": len(correct_answers),
        "results": results,
        "quiz_content": quiz_doc["quiz_data"],
    })

    return {
        "message":f"Quiz complete, You scored {score}/{len(correct_answers)}",
        "score":score,
        "total":len(correct_answers),
        "results":results
    }

@router.get("/quiz/history")
async def get_quiz_history(user=Depends(authenticate)):
    if user["role"] != "Student":
        raise HTTPException(status_code=403, detail="Only students can view quiz history")

    history = list(quiz_history.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("timestamp", -1))

    return {
        "total_quizzes": len(history),
        "history": history
    }