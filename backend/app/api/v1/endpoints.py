import logging

from fastapi import APIRouter

from .endpoint_modules.admin import router as admin_router
from .endpoint_modules.gazetteer import router as gazetteer_router
from .endpoint_modules.home import router as home_router
from .endpoint_modules.map import router as map_router
from .endpoint_modules.mcp import router as mcp_router
from .endpoint_modules.ogm import router as ogm_router
from .endpoint_modules.ogm_webhook import router as ogm_webhook_router
from .endpoint_modules.resources import router as resources_router

# Import all endpoint modules
from .endpoint_modules.root import router as root_router
from .endpoint_modules.search import router as search_router
from .endpoint_modules.shapefiles import router as shapefiles_router
from .endpoint_modules.static_maps import router as static_maps_router
from .endpoint_modules.thumbnails import router as thumbnails_router

logger = logging.getLogger(__name__)

router = APIRouter()

# Include all endpoint modules
router.include_router(root_router, tags=["root"])
router.include_router(search_router, tags=["search"])
router.include_router(home_router, tags=["home"])
router.include_router(resources_router, tags=["resources"])
router.include_router(thumbnails_router, tags=["thumbnails"])
router.include_router(static_maps_router, tags=["static-maps"])
router.include_router(map_router, tags=["map"])
router.include_router(mcp_router, tags=["mcp"])
router.include_router(ogm_router, tags=["ogm"])
# Hide admin, gazetteer, and shapefiles endpoints from Swagger documentation
router.include_router(admin_router, prefix="/admin", tags=["admin"], include_in_schema=False)
router.include_router(ogm_webhook_router, prefix="/admin", tags=["admin"], include_in_schema=False)
router.include_router(gazetteer_router, tags=["gazetteers"], include_in_schema=False)
router.include_router(shapefiles_router, tags=["shapefiles"], include_in_schema=False)
