from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class Post(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    description: str
    created_at: datetime = datetime.now()


class PostRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    description: str


class PostResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: str
    description: str
    created_at: datetime


class Comment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    post_id: int
    # user_id: int
    content: str
    timestamp: Optional[datetime] = None


class CommentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    post_id: int
    # user_id: int
    content: str
    timestamp: Optional[datetime] = None

    # class Config:
    #     from_attributes = True

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    post_id: int
    # user_id: int
    content: str
    timestamp: Optional[datetime] = None    

    # class Config:
    #     from_attributes = True