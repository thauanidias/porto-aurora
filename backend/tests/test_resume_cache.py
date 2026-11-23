from unittest.mock import Mock

from app.core.security import decrypt
from app.services.resume_cache import read_result, result_key, store_result


def test_cache_encrypts_data_and_is_scoped_to_owner_and_file(monkeypatch):
    client = Mock()
    storage = {}

    def put(key, ttl, value):
        storage[key] = value
        assert ttl == 3600

    client.setex.side_effect = put
    client.get.side_effect = lambda key: storage.get(key)
    monkeypatch.setattr("app.services.resume_cache.Redis.from_url", lambda *args: client)
    result = {"suggestions": {"name": "Pessoa Teste"}, "text": "Nome: Pessoa Teste"}
    store_result("owner", "file-a", result)
    encrypted = storage[result_key("owner", "file-a")]
    assert "Pessoa Teste" not in encrypted
    assert "Pessoa Teste" in decrypt(encrypted)
    assert read_result("owner", "file-a") == result
    assert read_result("someone-else", "file-a") is None
    assert read_result("owner", "file-b") is None


def test_corrupted_cache_does_not_prevent_new_analysis(monkeypatch):
    client = Mock()
    client.get.return_value = b"invalid"
    monkeypatch.setattr("app.services.resume_cache.Redis.from_url", lambda *args: client)
    assert read_result("owner", "file") is None
