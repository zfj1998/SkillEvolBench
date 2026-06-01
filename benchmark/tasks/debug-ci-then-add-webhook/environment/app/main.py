"""
EventHub API — FastAPI application.

Routes:
  GET  /api/users         — list all user profiles
  GET  /api/users/{id}    — single user profile
  GET  /api/users/active  — active users only
  POST /api/webhooks      — receive webhook events
  GET  /api/health        — health check
"""

from fastapi import FastAPI
from app.routers import users, webhooks

app = FastAPI(title='EventHub', version='3.1.0')

app.include_router(users.router, prefix='/api')
app.include_router(webhooks.router, prefix='/api')


@app.get('/api/health')
async def health():
    return {'status': 'ok'}
