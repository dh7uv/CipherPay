import pytest


@pytest.fixture(autouse=True)
def isolate_api_test_state(request, monkeypatch):
    if request.module.__name__ not in {"test_app", "test_auth", "test_simulations"}:
        yield
        return

    from backend import database
    from backend.main import app
    from backend.routes import auth as auth_routes
    from backend.routes import transactions as transaction_routes
    from backend.services.redis_service import redis_service

    async def mongo_unavailable():
        return False

    monkeypatch.setattr(database, "_mongo_ready", False)
    monkeypatch.setattr(database, "ping_database", mongo_unavailable)
    monkeypatch.setattr(auth_routes.settings, "redis_rate_limit", 100_000)
    monkeypatch.setattr(transaction_routes.settings, "redis_rate_limit", 100_000)
    for collection in app.state.store.values():
        collection.clear()
    redis_service.reset("ratelimit:testclient:auth_register")
    yield
