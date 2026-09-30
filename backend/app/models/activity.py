from sqlalchemy import Column, DateTime, Integer, String, Text, func, text

from app.database import Base
from app.utils.business_id import generate_business_id


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(String(32), unique=True, nullable=False, index=True, default=generate_business_id)
    title = Column(String(200), nullable=False, default="", server_default="", index=True)
    image_url = Column(String(500), nullable=False, default="", server_default="")
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="enabled", server_default="enabled", index=True)
    sort_order = Column(Integer, nullable=False, default=100, server_default="100", index=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())
