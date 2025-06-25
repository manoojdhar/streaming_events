from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import datetime
import uvicorn
from models import CommentRequest, CommentResponse, PostRequest, PostResponse
from database import SessionLocal, Comment
import json
from typing import Dict, List
import asyncio

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],  # Adjust this to match your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Cache-Control", "Connection", "X-Accel-Buffering"],  # Required for SSE
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns status information about the service
    """
    return {
        "status": "healthy",
        "service": "Commenting Service",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/posts")
async def create_post(post_data: PostRequest, db: SessionLocal = Depends(get_db)):
    """
    Create a new post
    """
    # Get the next available post ID (assuming sequential IDs)
    last_post = db.query(Comment).order_by(Comment.post_id.desc()).first()
    new_post_id = 1 if last_post is None else last_post.post_id + 1

    # Create a placeholder comment to store post information
    post = Comment(
        post_id=new_post_id,
        user_id=0,  # Using 0 as a special user_id to indicate this is a post
        content=post_data.description,
        timestamp=datetime.now()
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # Return the post information
    return PostResponse(
        id=new_post_id,
        title=post_data.title,
        description=post_data.description,
        created_at=post.timestamp
    )

@app.get("/posts", response_model=list[PostResponse])
async def list_posts(db: SessionLocal = Depends(get_db)):
    """
    Get list of all posts
    """
    # Query all posts (comments with user_id=0)
    posts = db.query(Comment).filter(Comment.user_id == 0).all()
    return [
        PostResponse(
            id=post.post_id,
            title=post.content.split('\n')[0],  # Extract title from content
            description=post.content,
            created_at=post.timestamp
        )
        for post in posts
    ]

@app.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: SessionLocal = Depends(get_db)):
    """
    Get details of a specific post
    """
    # Query the post (comment with user_id=0 and matching post_id)
    post = db.query(Comment).filter(
        Comment.user_id == 0,
        Comment.post_id == post_id
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return PostResponse(
        id=post.post_id,
        title=post.content.split('\n')[0],  # Extract title from content
        description=post.content,
        created_at=post.timestamp
    )

@app.post("/comments", response_model=CommentResponse)
async def create_comment(request: CommentRequest, db: SessionLocal = Depends(get_db)):
    try:
        post_id = request.post_id
        # user_id = request.user_id
        content = request.content

        if not post_id or not content:
            raise HTTPException(status_code=400, detail="Missing required fields")

        db_comment = Comment(
            post_id=post_id,
            # user_id=0,    
            content=content
        )
        
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)
        
        # Notify SSE clients
        if post_id in sse_clients:
            comment_data = serialize_comment(db_comment)
            message = json.dumps({
                'event': 'new_comment',
                'data': comment_data
            })
            
            # Put message in all client queues
            for client_queue in sse_clients[post_id]:
                try:
                    await client_queue.put(message)
                    print(f"Message put in queue: {message}")
                except Exception as e:
                    print(f"Error putting message in queue: {str(e)}")
                    continue
        
        return CommentResponse.model_validate(db_comment)
    except Exception as e:
        print(f"Error creating comment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# Store SSE clients
from asyncio import Queue

# Store SSE clients with async queues
sse_clients: Dict[int, List[Queue]] = {}

def serialize_comment(comment):
    """Helper function to serialize a comment with proper datetime handling"""
    return {
        'post_id': comment.post_id,
        'content': comment.content,
        'timestamp': comment.timestamp.isoformat() if comment.timestamp else None
    }

@app.get("/comments/stream/{post_id}")
async def comment_stream(request: Request, post_id: int, db: SessionLocal = Depends(get_db)):
    async def event_generator():
        try:
            # Send initial comments when client connects, ordered by newest first
            comments = db.query(Comment).filter(Comment.post_id == post_id)
            comments = comments.order_by(Comment.timestamp.desc()).all()
            
            # Send initial comments
            for comment in comments:
                comment_data = serialize_comment(comment)
                yield f"event: initial_comment\ndata: {json.dumps({
                    'event': 'initial_comment',
                    'data': comment_data
                })}\n\n"
            
            # Ensure we have a list for this post_id
            if post_id not in sse_clients:
                sse_clients[post_id] = []
            
            # Create a queue for this client
            client_queue = Queue()
            sse_clients[post_id].append(client_queue)
            
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    
                    try:
                        # Wait for a message from the queue with a timeout
                        message = await asyncio.wait_for(client_queue.get(), timeout=30)
                        # Add event header to new comments
                        # print("Ideate the message object", message)
                        yield f"event: new_comment\ndata: {message}\n\n"
                    except asyncio.TimeoutError:
                        # Send a keep-alive message
                        yield f":\n\n"  # SSE comment line
            finally:
                # Remove this client's queue
                if client_queue in sse_clients[post_id]:
                    sse_clients[post_id].remove(client_queue)
                    if not sse_clients[post_id]:
                        del sse_clients[post_id]
        except Exception as e:
            print(f"Error in SSE stream: {str(e)}")
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@app.get("/comments/{post_id}")
async def get_comments(post_id: int, db: SessionLocal = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.post_id == post_id).all()
    return [
        CommentResponse.model_validate(comment)
        for comment in comments
    ]

@app.get("/comments")
async def list_all_comments(db: SessionLocal = Depends(get_db)):
    comments = db.query(Comment).all()
    return [
        CommentResponse.model_validate(comment)
        for comment in comments
    ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
