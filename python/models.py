from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()

STATUS_DONE = "o"
STATUS_PENDING = "x"
STATUS_ABNORMAL = "△"
VALID_STATUSES = {STATUS_DONE, STATUS_PENDING, STATUS_ABNORMAL}
VALID_ROLES = {"admin", "manager", "user"}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    daily_checks = db.relationship("DailyCheck", back_populates="user", cascade="all, delete-orphan")
    abnormal_notes = db.relationship("AbnormalNote", back_populates="user", cascade="all, delete-orphan")
    confirmations = db.relationship("DailyConfirmation", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(30), nullable=False)
    category = db.Column(db.String(255), nullable=False)
    limit_time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    daily_checks = db.relationship("DailyCheck", back_populates="source_category")


class DailyCheck(db.Model):
    __tablename__ = "daily_checks"
    __table_args__ = (
        db.UniqueConstraint("user_id", "category_id", "date", name="uq_daily_check_user_category_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    symbol = db.Column(db.String(30), nullable=False)
    category = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    status = db.Column(db.String(5), nullable=False, default=STATUS_PENDING)
    limit_time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="daily_checks")
    source_category = db.relationship("Category", back_populates="daily_checks")
    abnormal_note = db.relationship("AbnormalNote", back_populates="daily_check", uselist=False, cascade="all, delete-orphan")


class AbnormalNote(db.Model):
    __tablename__ = "abnormal_notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    daily_check_id = db.Column(db.Integer, db.ForeignKey("daily_checks.id"), unique=True, nullable=False)
    symbol = db.Column(db.String(30), nullable=False)
    category = db.Column(db.String(255), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="abnormal_notes")
    daily_check = db.relationship("DailyCheck", back_populates="abnormal_note")


class DailyConfirmation(db.Model):
    __tablename__ = "daily_confirmations"
    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_confirmation_user_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    confirmed_by = db.Column(db.Integer, nullable=False)
    confirmed_by_name = db.Column(db.String(120), nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    signature_note = db.Column(db.Text, nullable=True)

    user = db.relationship("User", back_populates="confirmations")
