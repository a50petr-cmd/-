from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from kopilka.models import Base

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def init_db(url: str) -> None:
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    if url.startswith("sqlite"):
        _engine = create_engine(
            url,
            future=True,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    else:
        _engine = create_engine(url, future=True, pool_pre_ping=True)
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    if _Session is None:
        raise RuntimeError("База не инициализирована")
    db = _Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
