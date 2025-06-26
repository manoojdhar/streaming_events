from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from database import SessionLocal
from models import PostRequest, PostResponse, Comment
from typing import List

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=PostResponse)
async def create_post(post_data: PostRequest, db: SessionLocal = Depends(get_db)):
    """
    Create a new post
    """
    last_post = db.query(Comment).order_by(Comment.post_id.desc()).first()
    new_post_id = 1 if last_post is None else last_post.post_id + 1

    post = Comment(
        post_id=new_post_id,
        user_id=0,  # Using 0 as a special user_id to indicate this is a post
        content=post_data.description,
        timestamp=datetime.now()
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    return PostResponse(
        id=new_post_id,
        title=post_data.title,
        description=post_data.description,
        created_at=post.timestamp
    )

@router.get("/", response_model=List[PostResponse])
async def list_posts(db: SessionLocal = Depends(get_db)):
    """
    Get list of all posts
    """
    posts = db.query(Comment).filter(Comment.user_id == 0).all()
    return [
        PostResponse(
            id=post.post_id,
            title=post.content.split('\n')[0],
            description=post.content,
            created_at=post.timestamp
        )
        for post in posts
    ]

@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: SessionLocal = Depends(get_db)):
    """
    Get details of a specific post
    """
    post = db.query(Comment).filter(
        Comment.user_id == 0,
        Comment.post_id == post_id
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return PostResponse(
        id=post.post_id,
        title=post.content.split('\n')[0],
        description=post.content,
        created_at=post.timestamp
    )
