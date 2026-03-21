from collections.abc import Generator

from sqlalchemy.orm import Session

from app.storage.db import get_db_session


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()
