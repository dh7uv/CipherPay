import asyncio

from backend import main


def test_demo_analyst_is_seeded_when_other_users_already_exist(monkeypatch):
    store = main.app.state.store
    original_store = {name: list(records) for name, records in store.items()}
    unrelated_user = {
        "_id": "existing-standard-user",
        "email": "existing-user@example.com",
        "role": "user",
        "status": "active",
    }

    async def record_seed(*_args):
        assert len(_args) == 2

    monkeypatch.setattr(main.settings, "seed_demo_data", True)
    monkeypatch.setattr(main, "persist_document", record_seed)
    store["users"][:] = [unrelated_user]

    try:
        asyncio.run(main.seed_demo_data(store))
        assert any(
            user["email"] == "demo@cipherpay.local" and user["role"] == "analyst"
            for user in store["users"]
        )
        demo_transaction = next(
            transaction for transaction in store["transactions"]
            if transaction["transaction_id"] == "txn_demo_001"
        )
        assert demo_transaction["user_id"] == "demo-user"
        assert store["alerts"]
        assert store["audit_logs"]
    finally:
        for collection_name, documents in original_store.items():
            store[collection_name][:] = documents
