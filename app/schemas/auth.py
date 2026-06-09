
from pydantic import BaseModel

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class UserOut(BaseModel):
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True
