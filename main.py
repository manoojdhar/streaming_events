from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn
from src.posts.routes import router as posts_router
from src.comments.routes import router as comments_router

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

# Include routers
app.include_router(posts_router, prefix="/posts", tags=["posts"])
app.include_router(comments_router, prefix="/comments", tags=["comments"])

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
