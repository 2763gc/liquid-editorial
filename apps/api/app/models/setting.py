from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text
from app.db.base import Base

class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
