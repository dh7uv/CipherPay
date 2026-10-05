import asyncio

from backend import database


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length=None):
        return list(self.documents if length is None else self.documents[:length])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = documents or []
        self.indexes = []

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    def find(self, query, projection):
        assert query == {}
        return FakeCursor([
            {key: value for key, value in document.items() if projection.get(key) != 0}
            for document in self.documents
        ])

    async def replace_one(self, query, document, upsert=False):
        assert upsert
        self.documents = [
            item for item in self.documents if item.get("_id") != query["_id"]
        ]
        self.documents.append(dict(document))

    async def update_one(self, query, update):
        document = next(item for item in self.documents if item["_id"] == query["_id"])
        document.update(update["$set"])

    async def find_one(self, query):
        return next(
            (dict(item) for item in self.documents if item["_id"] == query["_id"]),
            None,
        )


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]

    async def command(self, command):
        assert command == "ping"
        return {"ok": 1}


def test_mongo_store_initializes_indexes_and_restores_records(monkeypatch):
    fake_database = FakeDatabase()
    fake_database["users"].documents.append({
        "_id": "restored-user",
        "email": "restored@example.com",
        "role": "user",
        "status": "active",
    })
    monkeypatch.setattr(database, "database", fake_database)
    monkeypatch.setattr(database, "_mongo_ready", False)
    store = {"users": [], "transactions": [], "alerts": [], "audit_logs": []}

    initialized = asyncio.run(database.initialize_store(store))

    assert initialized
    assert database.mongo_connected()
    assert store["users"][0]["_id"] == "restored-user"
    assert any(
        kwargs.get("unique")
        for _, kwargs in fake_database["users"].indexes
    )


def test_mongo_documents_are_upserted_and_alert_changes_are_persisted(monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(database, "database", fake_database)
    monkeypatch.setattr(database, "_mongo_ready", True)

    asyncio.run(database.persist_document("transactions", {
        "transaction_id": "txn-persisted", "amount": 125,
    }))

    transaction = fake_database["transactions"].documents[0]
    assert transaction["_id"] == "txn-persisted"
    assert transaction["amount"] == 125

    asyncio.run(database.persist_document("alerts", {"alert_id": "alert-persisted", "status": "Open"}))
    asyncio.run(database.update_document("alerts", "alert-persisted", {"status": "Resolved"}))
    assert fake_database["alerts"].documents[0]["status"] == "Resolved"


def test_mongo_transaction_reads_return_database_values_without_internal_id(monkeypatch):
    fake_database = FakeDatabase()
    fake_database["transactions"].documents.append({
        "_id": "txn-source-of-truth",
        "transaction_id": "txn-source-of-truth",
        "amount": 150,
    })
    monkeypatch.setattr(database, "database", fake_database)
    monkeypatch.setattr(database, "_mongo_ready", True)

    transaction = asyncio.run(database.get_document("transactions", "txn-source-of-truth"))

    assert transaction == {"transaction_id": "txn-source-of-truth", "amount": 150}
