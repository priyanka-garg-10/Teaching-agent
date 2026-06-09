from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .model import StudentUser, TeacherUser
from .hash_utils import hash_password, verify_password
from config.db import users_collection

router = APIRouter()
security= HTTPBasic()


def authenticate(credentials:HTTPBasicCredentials=Depends(security)):
    """Authenticates a user using HTTP Basic Auth"""
    user=users_collection.find_one({"username":credentials.username})
    if not user or not verify_password(credentials.password,user.get("password")):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "user_id": str(user["_id"]),
        "username": user["username"],
        "role": user.get("role"),
        "grade": user.get("grade"),
    }


@router.post("/signup/student")
def student_signup(req: StudentUser):
    """Handles a student signup request"""
    if users_collection.find_one({"email": req.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    if users_collection.find_one({"username": req.username}):
        raise HTTPException(status_code=400, detail="Username already taken")

    student_data = req.model_dump()
    student_data["password"] = hash_password(req.password)
    student_data["role"] = "Student"

    users_collection.insert_one(student_data)
    return {"message": "Student registered successfully"}


@router.post("/signup/teacher")
def teacher_signup(req: TeacherUser):
    """Handles a teacher signup request"""
    if users_collection.find_one({"email": req.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    if users_collection.find_one({"username": req.username}):
        raise HTTPException(status_code=400, detail="Username already taken")

    teacher_data = req.model_dump()
    teacher_data["password"] = hash_password(req.password)
    teacher_data["role"] = "Teacher"

    users_collection.insert_one(teacher_data)
    return {"message": "Teacher registered successfully"}


@router.get("/login")
def login(user: dict = Depends(authenticate)):
    return {"message": f"Login successful Welcome! {user['username']}!","role":user["role"]}

'''
# check for user credentials
@router.get("/me")
def me(user: dict = Depends(authenticate)):
    return user
'''