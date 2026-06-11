from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings

Base = declarative_base()


class BehaviorORM(Base):
    __tablename__ = "user_behaviors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    product_id = Column(Integer, index=True, nullable=False)
    action = Column(String(32), index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DatabaseManager:
    def __init__(self) -> None:
        self.engine = None
        self.session_factory = None
        self.init_error: str | None = None

    def init_engine(self) -> None:
        if self.engine is not None and self.session_factory is not None:
            return

        try:
            self.engine = create_engine(settings.database_url, pool_pre_ping=True)
            self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
            self.init_error = None
        except Exception as ex:  # pragma: no cover
            self.engine = None
            self.session_factory = None
            self.init_error = str(ex)

    def create_tables(self) -> None:
        self.init_engine()
        if self.engine is not None:
            Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        self.init_engine()
        if self.session_factory is None:
            raise HTTPException(
                status_code=503,
                detail=f"Không thể kết nối database: {self.init_error or 'khởi tạo thất bại'}",
            )
        return self.session_factory()


db_manager = DatabaseManager()
