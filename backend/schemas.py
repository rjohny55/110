from pydantic import BaseModel, Field
from typing import Optional


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class GameResponse(BaseModel):
    id: int
    board: list[str]
    status: str
    current_turn: str
    winner: Optional[str] = None
    player_x: str
    player_o: str = "computer"


class GameListItem(BaseModel):
    id: int
    status: str
    result: Optional[str] = None
    opponent: str = "computer"
    created_at: str


class MoveRequest(BaseModel):
    position: int = Field(..., ge=0, le=8)


class ErrorResponse(BaseModel):
    detail: str
