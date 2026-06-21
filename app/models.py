from sqlalchemy import Column, String, BigInteger, Float, DateTime, func
from app.database import Base


class SearchQuery(Base):
    __tablename__ = "search_queries"

    query = Column(String(255), primary_key=True, index=True)
    frequency = Column(BigInteger, default=0, nullable=False)
    # Unix timestamp of the last time this query was searched
    last_searched_at = Column(Float, default=0.0, nullable=False)
    # Accumulated recency score (exponentially decayed sum of searches)
    recency_score = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
