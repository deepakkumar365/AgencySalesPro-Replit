"""
Flask extensions initialization.
This module prevents circular imports by providing a central place for extension instances.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_caching import Cache
from sqlalchemy.orm import DeclarativeBase
import os

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
jwt = JWTManager()

# Helper to test Redis availability
def _test_redis_available():
    """Test if Redis is available"""
    try:
        import redis
        r = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        return True
    except Exception:
        return False

# Redis/Cache configuration
# Supports both Redis (if available) and simple dict-based caching
cache_type = os.environ.get("CACHE_TYPE", "redis")
if cache_type == "redis" and not _test_redis_available():
    cache_type = "simple"

cache_config = {
    "CACHE_TYPE": cache_type,
    "CACHE_REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    "CACHE_DEFAULT_TIMEOUT": 3600,  # 1 hour default timeout
}

cache = Cache(config=cache_config)