
import os
from datetime import datetime, timezone, timedelta

from flask import Flask, render_template, request, redirect, url_for, abort
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from app.models import db, User, Business, Review, ReplyVersion

RECYCLE_BIN_HOURS = 48


def naive_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get(
        "REVIEWPILOT_SECRET_KEY",
        "dev-only-change-this-before-deployment",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///reviewpilot.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    with app.app_context():
        db.create_all()

        if User.query.count() == 0:
            demo_user = User(email="demo@example.com", role="client")
            demo_user.set_password("DemoPassword123!")
            db.session.add(demo_user)
            db.session.flush()

            business = Business(
                owner_id=demo_user.id,
                name="Demo Business",
            )
            db.session.add(business)
            db.session.flush()

            sample_reviews = [
                Review(
                    business_id=business.id,
                    customer_name="Priya Sharma",
                    rating=5,
                    review_text="Excellent service! The staff was very helpful.",
                    reply_text="Thank you, Priya! We appreciate your kind words.",
                ),
                Review(
                    business_id=business.id,
                    customer_name="Rahul Kumar",
                    rating=2,
                    review_text="The delivery was late, and the service was disappointing.",
                    reply_text="We're sorry about your experience. We will work to improve.",
                ),
            ]

            db.session.add_all(sample_reviews)
            db.session.flush()

            for review in sample_reviews:
                db.session.add(
                    ReplyVersion(
                        review_id=review.id,
                        version=review.version,
                        reply_text=review.reply_text,
                        status=review.status,
                    )
                )

            db.session.commit()

    def cleanup_expired_versions():
        cutoff = naive_utc_now() - timedelta(hours=RECYCLE_BIN_HOURS)

        expired_versions = ReplyVersion.query.filter(
            ReplyVersion.is_deleted.is_(True),
            ReplyVersion.deleted_at.isnot(None),
            ReplyVersion.deleted_at <= cutoff,
        ).all()

        for version in expired_versions:
            db.session.delete(version)

        if expired_versions:
            db.session.commit()

    def get_review_or_404(review_id):
        review = db.session.get(Review, review_id)

        if review is None:
            abort(404)

        business = db.session.get(Business, review.business_id)

        if business is None or business.owner_id != current_user.id:
            abort(404)

        return review

    def get_version_or_404(version_id):
        version = db.session.get(ReplyVersion, version_id)

        if version is None:
            abort(404)

        review = db.session.get(Review, version.review_id)

        if review is None:
            abort(404)

        business = db.session.get(Business, review.business_id)

        if business is None or business.owner_id != current_user.id:
            abort(404)

        return version

    def move_current_version_to_bin(review, status, feedback=""):
        version = ReplyVersion.query.filter_by(
            review_id=review.id,
            version=review.version,
            is_deleted=False,
        ).order_by(ReplyVersion.id.desc()).first()

        if version is None:
            version = ReplyVersion(
                review_id=review.id,
                version=review.version,
                reply_text=review.reply_text,
                status=status,
            )
            db.session.add(version)
            db.session.flush()

        version.is_deleted = True
        version.deleted_at = naive_utc_now()
        version.status = status

        if feedback:
            review.feedback = feedback

    # Public website pages

    @app.route("/", endpoint="home")
    @app.route("/", endpoint="landing")
    def landing():
        return render_template(
            "landing.html",
            current_year=datetime.now(timezone.utc).year,
        )

    @app.route("/features")
    def features():
        return render_template(
            "features.html",
            current_year=datetime.now(timezone.utc).year,
        )

    @app.route("/pricing")
    def pricing():
        return render_template(
            "pricing.html",
            current_year=datetime.now(timezone.utc).year,
        )

    # Registration

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            business_name = request.form.get("business_name", "").strip()

            if not email or not password or not business_name:
                return "All fields are required.", 400

            if len(password) < 8:
                return "Password must be at least 8 characters.", 400

            if len(business_name) > 150:
                return "Business name must be 150 characters or fewer.", 400

            if User.query.filter_by(email=email).first():
                return "An account with this email already exists.", 409

            try:
                user = User(email=email, role="client")
                user.set_password(password)

                db.session.add(user)
                db.session.flush()

                business = Business(
                    owner_id=user.id,
                    name=business_name,
                )

                db.session.add(business)
                db.session.commit()

            except Exception:
                db.session.rollback()
                raise

            login_user(user)
            return redirect(url_for("dashboard"))

        return render_template("register.html")

    # Login

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=email).first()

            if user and user.is_active and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))

            return render_template(
                "login.html",
                error="Invalid email or password.",
            ), 401

        return render_template("login.html")

    # Logout

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    # Dashboard

    
    @app.route("/dashboard")
    @login_required
    def dashboard():
        cleanup_expired_versions()

        # Find this user's business
        businesses = Business.query.filter_by(
            owner_id=current_user.id
        ).all()

        # Create a business if the account has none
        if not businesses:
            business = Business(
                owner_id=current_user.id,
                name="My Business",
            )
            db.session.add(business)
            db.session.commit()
            businesses = [business]

        # Add sample reviews only if this account has no reviews
        existing_review = Review.query.filter(
            Review.business_id.in_([b.id for b in businesses])
        ).first()

        if existing_review is None:
            sample_reviews = [
                {
                    "customer": "Priya Sharma",
                    "rating": 5,
                    "text": "Excellent service! The staff was very helpful.",
                    "reply": "Thank you, Priya! We appreciate your kind words.",
                },
                {
                    "customer": "Rahul Kumar",
                    "rating": 2,
                    "text": "The delivery was late and the service was disappointing.",
                    "reply": "We're sorry about your experience. We will work to improve.",
                },
                {
                    "customer": "Ananya Singh",
                    "rating": 4,
                    "text": "Good experience overall. The team was friendly.",
                    "reply": "Thank you for your feedback, Ananya!",
                },
            ]

            for item in sample_reviews:
                review = Review(
                    business_id=businesses[0].id,
                    customer_name=item["customer"],
                    rating=item["rating"],
                    review_text=item["text"],
                    reply_text=item["reply"],
                    status="Awaiting approval",
                    version=1,
                )
                db.session.add(review)
                db.session.flush()

                version = ReplyVersion(
                    review_id=review.id,
                    version=1,
                    reply_text=review.reply_text,
                    status=review.status,
                )
                db.session.add(version)

            db.session.commit()

        # Load this account's active reviews
        reviews = (
            Review.query.join(Business)
            .filter(
                Business.owner_id == current_user.id,
                Review.is_deleted.is_(False),
            )
            .order_by(Review.id)
            .all()
        )

        # Load this account's deleted reply versions
        recycle_bin = (
            ReplyVersion.query.join(Review)
            .join(Business)
            .filter(
                Business.owner_id == current_user.id,
                ReplyVersion.is_deleted.is_(True),
            )
            .order_by(ReplyVersion.deleted_at.desc())
            .all()
        )

        return render_template(
            "dashboard.html",
            reviews=reviews,
            total_reviews=len(reviews),
            awaiting_count=sum(
                r.status == "Awaiting approval" for r in reviews
            ),
            published_count=sum(
                r.status == "Published" for r in reviews
            ),
            recycle_bin=recycle_bin,
        )


    # Approve a reply

    @app.route("/approve/<int:review_id>", methods=["POST"])
    @login_required
    def approve(review_id):
        review = get_review_or_404(review_id)

        if (
            not review.is_deleted
            and review.status == "Awaiting approval"
        ):
            review.status = "Approved"
            review.approved_version = review.version
            review.approved_at = naive_utc_now()
            review.approved_by = current_user.id

            db.session.add(
                ReplyVersion(
                    review_id=review.id,
                    version=review.version,
                    reply_text=review.reply_text,
                    status="Approved",
                )
            )

            db.session.commit()

        return redirect(url_for("dashboard"))

    # Reject a reply draft

    @app.route("/reject/<int:review_id>", methods=["POST"])
    @login_required
    def reject(review_id):
        review = get_review_or_404(review_id)

        if (
            not review.is_deleted
            and review.status in (
                "Awaiting approval",
                "Approved",
                "Changes requested",
            )
        ):
            move_current_version_to_bin(review, "Rejected")

            review.status = "Changes requested"
            review.approved_version = None
            review.approved_at = None
            review.approved_by = None

            db.session.commit()

        return redirect(url_for("dashboard"))

    # Request changes

    @app.route("/request-changes/<int:review_id>", methods=["POST"])
    @login_required
    def request_changes(review_id):
        review = get_review_or_404(review_id)
        feedback = request.form.get("feedback", "").strip()

        if (
            not review.is_deleted
            and review.status == "Awaiting approval"
            and feedback
        ):
            move_current_version_to_bin(
                review,
                "Changes requested",
                feedback,
            )

            review.status = "Changes requested"
            review.approved_version = None
            review.approved_at = None
            review.approved_by = None

            db.session.commit()

        return redirect(url_for("dashboard"))

    # Revise a reply

    @app.route("/revise/<int:review_id>", methods=["POST"])
    @login_required
    def revise(review_id):
        review = get_review_or_404(review_id)
        new_reply = request.form.get("reply", "").strip()

        if (
            not review.is_deleted
            and review.status == "Changes requested"
            and new_reply
        ):
            review.reply_text = new_reply
            review.version += 1
            review.status = "Awaiting approval"
            review.feedback = ""
            review.approved_version = None
            review.approved_at = None
            review.approved_by = None

            db.session.add(
                ReplyVersion(
                    review_id=review.id,
                    version=review.version,
                    reply_text=review.reply_text,
                    status="Awaiting approval",
                )
            )

            db.session.commit()

        return redirect(url_for("dashboard"))

    # Recycle bin

    @app.route("/recycle-bin")
    @login_required
    def recycle_bin():
        cleanup_expired_versions()

        versions = (
            ReplyVersion.query.join(
                Review,
                ReplyVersion.review_id == Review.id,
            )
            .join(
                Business,
                Review.business_id == Business.id,
            )
            .filter(
                Business.owner_id == current_user.id,
                ReplyVersion.is_deleted.is_(True),
            )
            .order_by(ReplyVersion.deleted_at.desc())
            .all()
        )

        return render_template(
            "recycle_bin.html",
            versions=versions,
            recycle_bin_hours=RECYCLE_BIN_HOURS,
        )

    # Restore a reply version

    @app.route("/restore-version/<int:version_id>", methods=["POST"])
    @login_required
    def restore_version(version_id):
        version = get_version_or_404(version_id)

        if not version.is_deleted or version.deleted_at is None:
            return redirect(url_for("recycle_bin"))

        deadline = version.deleted_at + timedelta(
            hours=RECYCLE_BIN_HOURS
        )

        if naive_utc_now() >= deadline:
            db.session.delete(version)
            db.session.commit()
            return redirect(url_for("recycle_bin"))

        review = get_review_or_404(version.review_id)

        if review.is_deleted:
            abort(
                409,
                description=(
                    "Restore the customer review before restoring this version."
                ),
            )

        review.reply_text = version.reply_text
        review.version = max(review.version, version.version) + 1
        review.status = "Awaiting approval"
        review.feedback = ""
        review.approved_version = None
        review.approved_at = None
        review.approved_by = None

        version.is_deleted = False
        version.deleted_at = None
        version.status = "Restored"

        db.session.add(
            ReplyVersion(
                review_id=review.id,
                version=review.version,
                reply_text=review.reply_text,
                status="Awaiting approval",
            )
        )

        db.session.commit()
        return redirect(url_for("recycle_bin"))

    # Permanently delete a reply version

    @app.route(
        "/permanent-delete-version/<int:version_id>",
        methods=["POST"],
    )
    @login_required
    def permanent_delete_version(version_id):
        version = get_version_or_404(version_id)

        if version.is_deleted:
            db.session.delete(version)
            db.session.commit()

        return redirect(url_for("recycle_bin"))

    return app
