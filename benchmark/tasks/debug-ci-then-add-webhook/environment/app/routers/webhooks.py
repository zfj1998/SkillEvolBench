"""Webhook route for EventHub."""

from fastapi import APIRouter, Request

router = APIRouter(tags=['webhooks'])


@router.post('/webhooks')
async def receive_webhook(request: Request):
    raise NotImplementedError('Webhook endpoint still needs to be implemented')
