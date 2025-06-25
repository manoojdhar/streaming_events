import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';

const PostDetails = () => {
  const { postId } = useParams();
  const [post, setPost] = useState(null);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState('');
  const [eventSource, setEventSource] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Constants
  const BATCH_DELAY = 100;
  const updatePriority = {
    new_comment: 1,
    comment_update: 2,
    comment_delete: 3
  };

  // Efficient data structures for comments
  const commentsMap = useRef(new Map());
  const cachedComments = useRef([]);
  const batchUpdates = useRef([]);
  const batchTimer = useRef(null);

  // Performance monitoring
  const measureLatency = useCallback((eventType) => {
    const now = Date.now();
    const latency = now - (commentsMap.current.lastUpdate || now);
    commentsMap.current.lastUpdate = now;
    console.log(`${eventType} latency: ${latency}ms`);
  }, []);

  // Batch updates
  const batchedUpdate = useCallback(() => {
    if (batchUpdates.current.length === 0) return;
    
    // Update state with functional update
    setComments(prevComments => {
      // Get existing comments
      const currentComments = [...prevComments];
      
      // Add new comments that aren't already in the list
      const newComments = batchUpdates.current.filter(comment => 
        !currentComments.some(existing => existing.id === comment.id)
      );
      
      // Combine existing and new comments
      const allComments = [...currentComments, ...newComments];
      
      // Sort comments by timestamp (newest first)
      const sortedComments = allComments.sort((a, b) => 
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      
      // Update cache
      cachedComments.current = sortedComments;
      commentsMap.current.clear();
      sortedComments.forEach(comment => commentsMap.current.set(comment.id, comment));
      
      // Clear batch updates
      batchUpdates.current = [];
      
      measureLatency('batch update');
      return sortedComments;
    });
  }, []);

  // Handle comment updates
  const handleCommentUpdate = useCallback((comment) => {
    if (commentsMap.current.has(comment.id)) {
      // Update the comment in the map
      commentsMap.current.set(comment.id, comment);
      
      // Find index in current comments
      const index = cachedComments.current.findIndex(c => c.id === comment.id);
      if (index !== -1) {
        // Update cache immediately
        cachedComments.current[index] = comment;
        
        // Update state with functional update
        setComments(prevComments => {
          // Create a copy of existing comments
          const newComments = [...prevComments];
          
          // Replace the comment at the found index
          newComments[index] = comment;
          
          // Sort comments by timestamp (newest first)
          const sortedComments = newComments.sort((a, b) => 
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          );
          
          return sortedComments;
        });
        
        // No need to trigger batch update since we've updated state directly
      }
    }
  }, []);

  // Handle comment deletion
  const handleCommentDelete = useCallback((commentId) => {
    if (commentsMap.current.has(commentId)) {
      // Remove from map
      commentsMap.current.delete(commentId);
      
      // Find index in cached comments
      const index = cachedComments.current.findIndex(c => c.id === commentId);
      if (index !== -1) {
        // Update cache
        cachedComments.current.splice(index, 1);
        
        // Update state with functional update
        setComments(prevComments => {
          const newComments = [...prevComments];
          newComments.splice(index, 1);
          
          // Sort remaining comments by timestamp (newest first)
          const sortedComments = newComments.sort((a, b) => 
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          );
          
          return sortedComments;
        });
      }
    }
  }, []);

  // Connect to SSE
  const connectToSSE = useCallback(() => {
    if (eventSource) {
      eventSource.close();
    }

    const source = new EventSource(`http://localhost:8000/comments/stream/${postId}`);
    setEventSource(source);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.event in updatePriority) {
          const priority = updatePriority[data.event];
          const comment = data.data;
          
          // Handle comment updates based on priority
          switch (data.event) {
            case 'new_comment':
              if (!commentsMap.current.has(comment.id)) {
                // Add to batch updates
                batchUpdates.current.push(comment);
                commentsMap.current.set(comment.id, comment);
                
                // Update state immediately for UI feedback
                setComments(prevComments => {
                  const newComments = [...prevComments, comment];
                  return newComments.sort((a, b) => 
                    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
                  );
                });
              }
              break;
            case 'comment_update':
              handleCommentUpdate(comment);
              break;
            case 'comment_delete':
              handleCommentDelete(comment.id);
              break;
          }

          // Start batch timer if not already running
          if (!batchTimer.current) {
            batchTimer.current = setTimeout(() => {
              // Process batch updates
              if (batchUpdates.current.length > 0) {
                setComments(prevComments => {
                  // Get existing comments
                  const currentComments = [...prevComments];
                  
                  // Add new comments
                  const newComments = [...currentComments, ...batchUpdates.current];
                  
                  // Sort by timestamp (newest first)
                  const sortedComments = newComments.sort((a, b) => 
                    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
                  );
                  
                  // Clear batch updates
                  batchUpdates.current = [];
                  
                  return sortedComments;
                });
              }
              batchTimer.current = null;
            }, BATCH_DELAY);
          }

          measureLatency('comment received');
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error);
        source.close(); // Close on parse error
      }
    };

    source.onerror = (error) => {
      console.error('SSE connection error:', error);
      source.close();
      setError('Connection lost. Attempting to reconnect...');
      
      // Prevent immediate reconnection
      const retryAttempts = localStorage.getItem('retryAttempts') || 0;
      if (retryAttempts < 5) { // Maximum 5 retries
        const retryDelay = Math.min(50 * Math.pow(2, retryAttempts), 1000);
        localStorage.setItem('retryAttempts', retryAttempts + 1);
        
        setTimeout(() => {
          localStorage.setItem('retryAttempts', 0);
          setError(''); // Clear error when attempting reconnect
          connectToSSE();
        }, retryDelay);
      } else {
        // After 5 retries, stop attempting to reconnect
        setError('Maximum retry attempts reached. Please refresh the page.');
        console.error('Maximum retry attempts reached. Please refresh the page.');
      }
    };

    source.onopen = () => {
      console.log('SSE connection established');
      localStorage.setItem('retryAttempts', 0);
      measureLatency('connection established');
    };

    return source;
  }, [postId]);

  // Load post
  const loadPost = useCallback(async () => {
    try {
      const response = await fetch(`http://localhost:8000/posts/${postId}`);
      if (response.ok) {
        const data = await response.json();
        setPost(data);
      }
    } catch (error) {
      console.error('Error loading post:', error);
    }
  }, [postId]);

  // Load initial comments
  const loadInitialComments = useCallback(async () => {
    try {
      const response = await fetch(`http://localhost:8000/comments/${postId}`);
      if (!response.ok) {
        throw new Error('Failed to load comments');
      }
      const data = await response.json();
      
      // Sort initial comments by timestamp (newest first)
      const sortedComments = data.sort((a, b) => 
        new Date(b.timestamp) - new Date(a.timestamp)
      );
      
      // Update state and cache
      setComments(sortedComments);
      cachedComments.current = sortedComments;
      commentsMap.current.clear();
      sortedComments.forEach(comment => commentsMap.current.set(comment.id, comment));
    } catch (error) {
      console.error('Error loading comments:', error);
      setError('Failed to load comments');
    } finally {
      setLoading(false);
    }
  }, [postId]);

  // Handle comment submission
  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    try {
      const response = await fetch('http://localhost:8000/comments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          post_id: postId,
          content: newComment
        })
      });

      if (response.ok) {
        // Clear the input
        setNewComment('');
        
        // Get the newly created comment from the response
        const newCommentData = await response.json();
        
        // Update state immediately with the new comment
        setComments(prevComments => {
          const newComments = [...prevComments, newCommentData];
          return newComments.sort((a, b) => 
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          );
        });
      } else {
        console.error('Error posting comment');
      }
    } catch (error) {
      console.error('Error posting comment:', error);
    }
  }, [newComment, postId]);

  // Main useEffect
  useEffect(() => {
    if (!postId) return;

    // Load initial data
    loadPost();
    loadInitialComments();

    // Connect to SSE
    const source = connectToSSE();

    // Add a health check
    const healthCheck = () => {
      if (source.readyState !== EventSource.OPEN) {
        console.log('SSE connection not healthy, attempting reconnect');
        const retryAttempts = localStorage.getItem('retryAttempts') || 0;
        if (retryAttempts < 5) { // Only attempt reconnect if under retry limit
          connectToSSE();
        }
      }
    };

    // Run health check every second
    const healthCheckInterval = setInterval(healthCheck, 1000);

    // Cleanup
    return () => {
      if (source) {
        source.close();
      }
      clearInterval(healthCheckInterval);
      localStorage.removeItem('retryAttempts');
    };
  }, [postId, connectToSSE]);

  if (!post) return <div>Loading...</div>;

  return (
    <div key="post-details-container" className="post-details-container">
      <div key="post-header" className="post-header">
        <h1 key="post-title">{post.title}</h1>
        <p key="post-meta" className="post-meta">
          Created: {new Date(post.created_at).toLocaleString()}
        </p>
        <p key="post-description" className="post-description">{post.description}</p>
      </div>

      <div key="comments-section" className="comments-section">
        <h2 key="comments-header">Comments</h2>
        
        <div key="comments-list" className="comments-list">
          {loading && (
            <div key="loading-state" className="loading">Loading comments...</div>
          )}
          {error && (
            <div key="error-state" className="error">{error}</div>
          )}
          {(!loading && !error) && (
            <>
              {comments.length === 0 && (
                <div key="no-comments-state" className="no-comments">No comments yet. Be the first to comment!</div>
              )}
              {comments.map((comment) => (
                <div key={comment.id} className="comment-box">
                  <div key={`comment-header-${comment.id}`} className="comment-header">
                    <strong>Anonymous</strong>
                    <span key={`comment-timestamp-${comment.id}`} className="comment-timestamp">
                      {new Date(comment.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div key={`comment-content-${comment.id}`} className="comment-content">
                    {comment.content}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        <form key="comment-form" onSubmit={handleSubmit} className="comment-form">
          <textarea
            key="comment-textarea"
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Add a comment..."
            required
          />
          <button key="comment-submit" type="submit">Post Comment</button>
        </form>
      </div>
    </div>
  );
};

export default PostDetails;
