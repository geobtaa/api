import logging

from fastapi import APIRouter

from .endpoint_modules.admin import router as admin_router
from .endpoint_modules.gazetteer import router as gazetteer_router
from .endpoint_modules.resources import router as resources_router

# Import all endpoint modules
from .endpoint_modules.root import router as root_router
from .endpoint_modules.search import router as search_router
from .endpoint_modules.shapefiles import router as shapefiles_router
from .endpoint_modules.thumbnails import router as thumbnails_router

logger = logging.getLogger(__name__)

router = APIRouter()

# Include all endpoint modules
router.include_router(root_router, tags=["root"])
router.include_router(resources_router, tags=["resources"])
router.include_router(search_router, tags=["search"])
router.include_router(thumbnails_router, tags=["thumbnails"])
router.include_router(admin_router, tags=["admin"])
router.include_router(gazetteer_router, tags=["gazetteers"])
router.include_router(shapefiles_router, tags=["shapefiles"])
