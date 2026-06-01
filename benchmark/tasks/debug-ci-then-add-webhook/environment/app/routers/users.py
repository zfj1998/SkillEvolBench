"""User API routes."""

from fastapi import APIRouter, HTTPException
from app import services

router = APIRouter(tags=['users'])


@router.get('/users')
async def list_users():
    return {'users': services.list_user_profiles()}


@router.get('/users/active')
async def list_active_users():
    return {'users': services.get_active_users()}


@router.get('/users/{user_id}')
async def get_user(user_id: int):
    profile = services.get_user_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail='User not found')
    return profile
