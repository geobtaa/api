from app import database


class FakeConnection:
    def __init__(self) -> None:
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def execute(self, statement) -> None:
        self.statement = statement


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.disposed = False

    def connect(self) -> FakeConnection:
        return self.connection

    async def dispose(self) -> None:
        self.disposed = True


async def test_database_check_executes_a_query(monkeypatch) -> None:
    engine = FakeEngine()
    monkeypatch.setattr(database, "get_engine", lambda: engine)

    await database.check_database()

    assert str(engine.connection.statement) == "SELECT 1"
