from pydantic import BaseModel
from typing import Optional

class CreateTeacher(BaseModel):
    name: str 
    email: str
    password: str

class CreateStudent(CreateTeacher):
    M_number: str

class UpdateTeacher(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None

class UpdateStudent(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None

class GetTeacher(BaseModel):
    id: int
    name: str
    email: str

class GetStudent(BaseModel):
    id: int
    name: str
    email: str
    