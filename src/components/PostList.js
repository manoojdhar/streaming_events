import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const PostList = () => {
  const [posts, setPosts] = useState([]);
  const [newPost, setNewPost] = useState({
    title: '',
    description: ''
  });
  const navigate = useNavigate();

  useEffect(() => {
    fetchPosts();
  }, []);

  const fetchPosts = async () => {
    try {
      const response = await fetch('http://localhost:8000/posts');
      if (response.ok) {
        const data = await response.json();
        setPosts(data);
      }
    } catch (error) {
      console.error('Error fetching posts:', error);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewPost(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const createPost = async () => {
    const { title, description } = newPost;
    
    if (!title.trim() || !description.trim()) {
      alert('Please fill in both title and description');
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/posts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title, description })
      });

      if (response.ok) {
        const newPost = await response.json();
        setPosts(prevPosts => [...prevPosts, newPost]);
        setNewPost({ title: '', description: '' });
      } else {
        console.error('Error creating post');
      }
    } catch (error) {
      console.error('Error creating post:', error);
    }
  };

  return (
    <div key="post-list-container" className="post-list-container">
      <h2 key="posts-header">Posts</h2>
      
      <div key="post-form" className="post-form">
        <input
          key="post-title-input"
          type="text"
          name="title"
          value={newPost.title}
          onChange={handleInputChange}
          placeholder="Post Title"
          required
        />
        <textarea
          key="post-description-input"
          name="description"
          value={newPost.description}
          onChange={handleInputChange}
          placeholder="Post Description"
          required
        />
        <button key="create-post-btn" onClick={createPost} className="create-post-btn">
          Create Post
        </button>
      </div>

      <div key="posts-grid" className="posts-grid">
        {posts.map(post => (
          <div key={post.id} className="post-card" onClick={() => navigate(`/post/${post.id}`)}>
            <h3 key={`post-title-${post.id}`}>{post.title}</h3>
            <p key={`post-description-${post.id}`}>{post.description}</p>
            <span key={`post-meta-${post.id}`} className="post-meta">
              Created: {new Date(post.created_at).toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PostList;
