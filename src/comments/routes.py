from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from database import SessionLocal
from models import CommentRequest, CommentResponse, Comment
from typing import Dict, List
import json
import asyncio
from asyncio import Queue

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Store SSE clients
sse_clients: Dict[int, List[Queue]] = {}

def serialize_comment(comment):
    """Helper function to serialize a comment with proper datetime handling"""
    return {
        'post_id': comment.post_id,
        'content': comment.content,
        'timestamp': comment.timestamp.isoformat() if comment.timestamp else None
    }

@router.post("/", response_model=CommentResponse)
async def create_comment(request: CommentRequest, db: SessionLocal = Depends(get_db)):
    try:
        post_id = request.post_id
        content = request.content

        if not post_id or not content:
            raise HTTPException(status_code=400, detail="Missing required fields")

        db_comment = Comment(
            post_id=post_id,
            content=content,
            timestamp=datetime.now()
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
                except Exception as e:
                    print(f"Error putting message in queue: {str(e)}")
                    continue
        
        return CommentResponse.model_validate(db_comment)
    except Exception as e:
        print(f"Error creating comment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stream/{post_id}")
async def comment_stream(request: Request, post_id: int, db: SessionLocal = Depends(get_db)):
    async def event_generator():
        try:
            # Send initial comments when client connects
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
                        yield f"event: new_comment\ndata: {message}\n\n"
                    except asyncio.TimeoutError:
                        # Send a keep-alive message
                        yield ':keepalive\n\n'
                    except Exception as e:
                        print(f"Error in event stream: {str(e)}")
                        break
            finally:
                # Clean up the queue when client disconnects
                sse_clients[post_id].remove(client_queue)
                if not sse_clients[post_id]:
                    del sse_clients[post_id]
        except Exception as e:
            print(f"Error in comment stream: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/{post_id}", response_model=List[CommentResponse])
async def get_comments(post_id: int, db: SessionLocal = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.post_id == post_id).all()
    return [CommentResponse.model_validate(comment) for comment in comments]

@router.get("/")
async def list_all_comments(db: SessionLocal = Depends(get_db)):
    comments = db.query(Comment).all()
    return [CommentResponse.model_validate(comment) for comment in comments]
