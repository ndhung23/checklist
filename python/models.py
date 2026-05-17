from __future__ import annotations

from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()

ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_LEADER = "leader"
ROLE_STAFF = "staff"
VALID_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_LEADER, ROLE_STAFF}

NOTIFICATION_UNREAD = "unread"
NOTIFICATION_READ = "read"
VALID_NOTIFICATION_STATUSES = {NOTIFICATION_UNREAD, NOTIFICATION_READ}

SHEET_STATUS_DRAFT = "draft"
SHEET_STATUS_CHECKING = "checking"
SHEET_STATUS_SUBMITTED = "submitted"
SHEET_STATUS_CONFIRMED = "confirmed"
SHEET_STATUS_REJECTED = "rejected"
VALID_SHEET_STATUSES = {
    SHEET_STATUS_DRAFT,
    SHEET_STATUS_CHECKING,
    SHEET_STATUS_SUBMITTED,
    SHEET_STATUS_CONFIRMED,
    SHEET_STATUS_REJECTED,
}

RESULT_OK = "o"
RESULT_NG = "x"
RESULT_ABNORMAL = "△"
RESULT_EMPTY = ""
VALID_RESULTS = {RESULT_OK, RESULT_NG, RESULT_ABNORMAL, RESULT_EMPTY}

ABNORMAL_STATUS_OPEN = "open"
ABNORMAL_STATUS_PROCESSING = "processing"
ABNORMAL_STATUS_FIXED = "fixed"
ABNORMAL_STATUS_CONFIRMED = "confirmed"
ABNORMAL_STATUS_CANCELLED = "cancelled"
VALID_ABNORMAL_STATUSES = {
    ABNORMAL_STATUS_OPEN,
    ABNORMAL_STATUS_PROCESSING,
    ABNORMAL_STATUS_FIXED,
    ABNORMAL_STATUS_CONFIRMED,
    ABNORMAL_STATUS_CANCELLED,
}


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'manager', 'leader', 'staff')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "gender IS NULL OR gender IN ('male', 'female', 'other')",
            name="ck_users_gender",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    employee_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    outlook_email = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    department = db.Column(db.String(120), nullable=False)
    line_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STAFF)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    leader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    manager = db.relationship(
        "User",
        remote_side=[id],
        foreign_keys=[manager_id],
        backref="managed_users",
    )
    leader = db.relationship(
        "User",
        remote_side=[id],
        foreign_keys=[leader_id],
        backref="led_users",
    )
    daily_sheets = db.relationship("DailyCheckSheet", back_populates="user")
    daily_results = db.relationship("DailyCheckResult", back_populates="user")
    abnormal_reports = db.relationship("AbnormalReport", back_populates="user")
    owned_confirmations = db.relationship(
        "DailyConfirmation",
        foreign_keys="DailyConfirmation.user_id",
        back_populates="user",
    )
    signed_confirmations = db.relationship(
        "DailyConfirmation",
        foreign_keys="DailyConfirmation.confirmed_by",
        back_populates="signer",
    )
    user_lines = db.relationship(
        "UserLine",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications = db.relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def can_confirm(self) -> bool:
        return self.role in {ROLE_ADMIN, ROLE_MANAGER, ROLE_LEADER}


class ChecklistTemplate(db.Model):
    __tablename__ = "checklist_templates"

    id = db.Column(db.Integer, primary_key=True)
    template_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    template_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    version = db.Column(db.String(50), nullable=False, default="1.0")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    checklist_items = db.relationship(
        "ChecklistItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ChecklistItem.item_order",
    )
    daily_sheets = db.relationship("DailyCheckSheet", back_populates="template")


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"
    __table_args__ = (
        UniqueConstraint("template_id", "line_id", "item_order", name="uq_checklist_items_template_line_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("checklist_templates.id"),
        nullable=False,
        index=True,
    )
    line_id = db.Column(db.Integer, db.ForeignKey("lines.id"), nullable=True, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    check_time = db.Column(db.Time, nullable=False, index=True)
    time_group = db.Column(db.String(100), nullable=False)
    item_order = db.Column(db.Integer, nullable=False)
    category_type = db.Column(db.String(50))
    content = db.Column(db.Text, nullable=False)
    content_vi = db.Column(db.Text, nullable=False)
    content_en = db.Column(db.Text)
    content_ja = db.Column(db.Text)
    note = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    template = db.relationship("ChecklistTemplate", back_populates="checklist_items")
    line = db.relationship("Line")
    daily_results = db.relationship("DailyCheckResult", back_populates="checklist_item")


class DailyCheckSheet(TimestampMixin, db.Model):
    __tablename__ = "daily_check_sheets"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "template_id",
            "check_date",
            name="uq_daily_check_sheet_user_template_date",
        ),
        CheckConstraint(
            "status IN ('draft', 'checking', 'submitted', 'confirmed', 'rejected')",
            name="ck_daily_check_sheets_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("checklist_templates.id"),
        nullable=False,
        index=True,
    )
    check_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    line_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    shift = db.Column(db.String(50), nullable=False, default="day")
    status = db.Column(db.String(20), nullable=False, default=SHEET_STATUS_DRAFT)

    user = db.relationship("User", back_populates="daily_sheets")
    template = db.relationship("ChecklistTemplate", back_populates="daily_sheets")
    results = db.relationship(
        "DailyCheckResult",
        back_populates="daily_sheet",
        cascade="all, delete-orphan",
    )
    abnormal_reports = db.relationship(
        "AbnormalReport",
        back_populates="daily_sheet",
        cascade="all, delete-orphan",
    )
    confirmations = db.relationship(
        "DailyConfirmation",
        back_populates="daily_sheet",
        cascade="all, delete-orphan",
    )


class DailyCheckResult(TimestampMixin, db.Model):
    __tablename__ = "daily_check_results"
    __table_args__ = (
        UniqueConstraint(
            "daily_sheet_id",
            "checklist_item_id",
            name="uq_daily_check_results_sheet_item",
        ),
        CheckConstraint(
            "result IN ('o', 'x', '△', '')",
            name="ck_daily_check_results_result",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    daily_sheet_id = db.Column(
        db.Integer,
        db.ForeignKey("daily_check_sheets.id"),
        nullable=False,
        index=True,
    )
    checklist_item_id = db.Column(
        db.Integer,
        db.ForeignKey("checklist_items.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    check_date = db.Column(db.Date, nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    check_time = db.Column(db.Time, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    result = db.Column(db.String(5), nullable=True, default=RESULT_EMPTY)
    checked_at = db.Column(db.DateTime)
    abnormal_note = db.Column(db.Text)
    leader_note = db.Column(db.Text)

    daily_sheet = db.relationship("DailyCheckSheet", back_populates="results")
    checklist_item = db.relationship("ChecklistItem", back_populates="daily_results")
    user = db.relationship("User", back_populates="daily_results")
    abnormal_reports = db.relationship(
        "AbnormalReport",
        back_populates="daily_check_result",
        cascade="all, delete-orphan",
    )


class AbnormalReport(TimestampMixin, db.Model):
    __tablename__ = "abnormal_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'processing', 'fixed', 'confirmed', 'cancelled')",
            name="ck_abnormal_reports_status",
        ),
        UniqueConstraint(
            "daily_check_result_id",
            name="uq_abnormal_reports_daily_result",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    daily_sheet_id = db.Column(
        db.Integer,
        db.ForeignKey("daily_check_sheets.id"),
        nullable=False,
        index=True,
    )
    daily_check_result_id = db.Column(
        db.Integer,
        db.ForeignKey("daily_check_results.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    occurred_date = db.Column(db.Date, nullable=False)
    abnormal_content = db.Column(db.Text, nullable=False)
    countermeasure = db.Column(db.Text)
    confirm_date_before_fix = db.Column(db.Date)
    result_after_fix = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default=ABNORMAL_STATUS_OPEN)

    daily_sheet = db.relationship("DailyCheckSheet", back_populates="abnormal_reports")
    daily_check_result = db.relationship("DailyCheckResult", back_populates="abnormal_reports")
    user = db.relationship("User", back_populates="abnormal_reports")


class DailyConfirmation(db.Model):
    __tablename__ = "daily_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "daily_sheet_id",
            "confirmed_role",
            name="uq_daily_confirmations_sheet_role",
        ),
        CheckConstraint(
            "confirmed_role IN ('admin', 'manager', 'leader')",
            name="ck_daily_confirmations_role",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    daily_sheet_id = db.Column(
        db.Integer,
        db.ForeignKey("daily_check_sheets.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    confirmed_by_name = db.Column(db.String(120), nullable=False)
    confirmed_role = db.Column(db.String(20), nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    signature_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    daily_sheet = db.relationship("DailyCheckSheet", back_populates="confirmations")
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="owned_confirmations",
    )
    signer = db.relationship(
        "User",
        foreign_keys=[confirmed_by],
        back_populates="signed_confirmations",
    )


class Line(db.Model):
    __tablename__ = "lines"

    id = db.Column(db.Integer, primary_key=True)
    line_name = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    user_lines = db.relationship(
        "UserLine",
        back_populates="line",
        cascade="all, delete-orphan",
    )


class UserLine(db.Model):
    __tablename__ = "user_lines"
    __table_args__ = (
        UniqueConstraint("user_id", "line_id", name="uq_user_lines_user_line"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    line_id = db.Column(db.Integer, db.ForeignKey("lines.id"), nullable=False, index=True)

    user = db.relationship("User", back_populates="user_lines")
    line = db.relationship("Line", back_populates="user_lines")


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        CheckConstraint(
            "status IN ('unread', 'read')",
            name="ck_notifications_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default="reminder", index=True)
    period_type = db.Column(db.String(20), nullable=False, index=True)
    target_date = db.Column(db.Date, nullable=False, index=True)
    related_sheet_id = db.Column(db.Integer, db.ForeignKey("daily_check_sheets.id"), nullable=True, index=True)
    dedupe_key = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=NOTIFICATION_UNREAD, index=True)
    read_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="notifications")
    related_sheet = db.relationship("DailyCheckSheet")
