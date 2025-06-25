import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import PostList from './components/PostList';
import PostDetails from './components/PostDetails';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="main-nav">
          <h1>Blog Posts</h1>
        </nav>
        
        <main>
          <Routes>
            <Route path="/" element={<PostList />} />
            <Route path="/post/:postId" element={<PostDetails />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
