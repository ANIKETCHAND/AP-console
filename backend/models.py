import datetime

try:
    from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
    from sqlalchemy.orm import relationship
    from database import Base
    HAS_SQLALCHEMY = True
except Exception:
    HAS_SQLALCHEMY = False
    Base = object

if HAS_SQLALCHEMY and Base is not object:
    class User(Base):
        """A person who has signed in with Google at least once."""

        __tablename__ = "users"

        id = Column(Integer, primary_key=True, index=True)
        google_sub = Column(String(64), unique=True, index=True, nullable=False)  # Google's stable user id
        email = Column(String(255), unique=True, index=True, nullable=False)
        name = Column(String(255))
        picture = Column(String(1024))
        created_at = Column(DateTime, default=datetime.datetime.utcnow)
        last_login_at = Column(DateTime, default=datetime.datetime.utcnow)

        cases = relationship("Case", back_populates="user", cascade="all, delete-orphan")


    class Case(Base):
        """One row per analysis/scan a signed-in user has run — powers the History tab."""

        __tablename__ = "cases"

        id = Column(Integer, primary_key=True, index=True)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
        case_type = Column(String(16), nullable=False)  # image | video | audio | intel
        label = Column(String(512), nullable=False)  # filename analyzed, or domain/email scanned
        verdict = Column(String(32))  # likely_manipulated/likely_authentic/uncertain, or risk level
        confidence = Column(Integer)  # manipulation confidence %, when applicable
        result_json = Column(Text, nullable=False)  # full API response, so a case can be reopened
        created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

        user = relationship("User", back_populates="cases")
else:
    class User:
        def __init__(self, id=1, email="caniket2007@gmail.com", name="Aniket Chand", picture=""):
            self.id = id
            self.email = email
            self.name = name
            self.picture = picture

    class Case:
        pass
