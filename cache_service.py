import json
import redis
from flask import current_app


def _client():
    return redis.Redis.from_url(current_app.config['REDIS_URL'], decode_responses=True, socket_connect_timeout=1)


def get_json(key):
    try:
        value = _client().get(key)
        return json.loads(value) if value else None
    except redis.RedisError:
        return None


def set_json(key, value, ttl=None):
    try:
        _client().setex(key, ttl or current_app.config['CACHE_TTL_SECONDS'], json.dumps(value))
        return True
    except redis.RedisError:
        return False


def delete_key(key):
    try:
        _client().delete(key)
    except redis.RedisError:
        pass


def redis_available():
    try:
        return bool(_client().ping())
    except redis.RedisError:
        return False
