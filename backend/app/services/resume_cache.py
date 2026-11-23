"""Short-lived encrypted results, scoped to owner, file, model and extractor version."""
import hashlib
import json

from cryptography.fernet import InvalidToken
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.security import decrypt, encrypt

EXTRACTOR_VERSION = "v8"


def result_key(owner_id: str, file_sha256: str) -> str:
    identity = f"{EXTRACTOR_VERSION}:{owner_id}:{file_sha256}:{settings().resume_ai_model}:{settings().resume_ai_enabled}"
    return "resume-result:" + hashlib.sha256(identity.encode()).hexdigest()


def read_result(owner_id: str, file_sha256: str) -> dict | None:
    client = Redis.from_url(settings().redis_url)
    try:
        stored = client.get(result_key(owner_id, file_sha256))
        if not stored:
            return None
        result = json.loads(decrypt(stored.decode() if isinstance(stored, bytes) else stored))
        return result if isinstance(result, dict) and isinstance(result.get("suggestions"), dict) else None
    except (RedisError, InvalidToken, ValueError, TypeError):
        return None
    finally:
        client.close()


def store_result(owner_id: str, file_sha256: str, result: dict) -> None:
    client = Redis.from_url(settings().redis_url)
    try:
        client.setex(result_key(owner_id, file_sha256), 3600, encrypt(json.dumps(result, ensure_ascii=False)))
    except RedisError:
        pass
    finally:
        client.close()
