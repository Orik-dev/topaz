"""Bot handlers."""
from aiogram import Router

from .start import router as start_router
from .balance import router as balance_router
from .process import router as process_router
from .admin import router as admin_router
from .webhook import router as webhook_router


def setup_routers() -> Router:
    """Setup all routers."""
    main_router = Router()
    
    # Order matters: more specific routes first
    main_router.include_router(admin_router)
    main_router.include_router(webhook_router)
    main_router.include_router(process_router)
    main_router.include_router(balance_router)
    main_router.include_router(start_router)
    
    return main_router