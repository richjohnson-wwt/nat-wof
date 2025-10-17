import pytest
import fakeredis


@pytest.fixture(scope="session")
def redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def _patch_shared_redis(monkeypatch, redis_client):
    # Patch wof_shared.redis_client.get_redis to return our fake client
    import wof_shared.redis_client as rc

    def _get():
        return redis_client

    monkeypatch.setattr(rc, "get_redis", _get, raising=True)
    # Clear DB before each test for isolation
    redis_client.flushdb()
    yield
    redis_client.flushdb()
