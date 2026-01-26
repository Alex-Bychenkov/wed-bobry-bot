"""Handlers package - telegram bot message and callback handlers."""
from aiogram import Router

from handlers.commands import router as commands_router
from handlers.callbacks import router as callbacks_router
from handlers.states import router as states_router
from handlers.keyboard import build_prompt_keyboard

# Main router that includes all sub-routers
router = Router()
router.include_router(commands_router)
router.include_router(callbacks_router)
router.include_router(states_router)

__all__ = ["router", "build_prompt_keyboard"]
