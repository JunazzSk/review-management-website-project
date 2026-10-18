from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin,db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="client")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    businesses = db.relationship(
        "Business",
        backref="owner",
        cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Business(db.Model):
    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    reviews = db.relationship(
        "Review",
        backref="business",
        cascade="all, delete-orphan"
    )


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("businesses.id"),
        nullable=False,
        index=True
    )
    customer_name = db.Column(db.String(150), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    reply_text = db.Column(db.Text, nullable=False, default="")
    status = db.Column(
        db.String(30),
        nullable=False,
        default="Awaiting approval"
    )
    feedback = db.Column(db.Text, nullable=False, default="")
    version = db.Column(db.Integer, nullable=False, default=1)

    # Recycle Bin fields
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    deleted_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    # Approval tracking
    approved_version = db.Column(db.Integer, nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)


class ReplyVersion(db.Model):
    __tablename__ = "reply_versions"

    id = db.Column(db.Integer, primary_key=True)

    review_id = db.Column(
        db.Integer,
        db.ForeignKey("reviews.id"),
        nullable=False,
        index=True
    )

    version = db.Column(db.Integer, nullable=False)
    reply_text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False)

    # Recycle Bin fields for this specific reply version
    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now
    )

    review = db.relationship(
        "Review",
        backref=db.backref("reply_versions", cascade="all, delete-orphan")
    )


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True
    )
    plan_name = db.Column(db.String(50), nullable=False, default="free")
    status = db.Column(db.String(30), nullable=False, default="inactive")
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    user = db.relationship(
        "User",
        backref=db.backref("subscription", uselist=False)
    )