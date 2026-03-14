from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import auth_bp
from app.extensions import db
from app.models.user import InviteToken, User


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(url_for("characters.character_list"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            if next_page and urlparse(next_page).netloc:
                next_page = None
            return redirect(next_page or url_for("characters.character_list"))

        flash("Invalid username or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registration page."""
    if current_user.is_authenticated:
        return redirect(url_for("characters.character_list"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for("characters.character_list"))

    return render_template("auth/register.html")


@auth_bp.route("/invite", methods=["POST"])
@login_required
def create_invite():
    """Generate a single-use invite token and return a copyable link."""
    token = InviteToken(created_by=current_user.id)
    db.session.add(token)
    db.session.commit()
    invite_url = url_for("auth.register_with_token", token=token.token, _external=True)
    return render_template("partials/invite_link.html", invite_url=invite_url)


@auth_bp.route("/register/<token>", methods=["GET", "POST"])
def register_with_token(token: str):
    """Register using an invite token."""
    if current_user.is_authenticated:
        return redirect(url_for("characters.character_list"))

    invite = InviteToken.query.filter_by(token=token).first()
    if not invite:
        flash("Invalid invite link.", "error")
        return redirect(url_for("auth.login"))
    if invite.used_by is not None:
        flash("This invite has already been used.", "error")
        return redirect(url_for("auth.login"))
    if invite.expires_at and datetime.now(timezone.utc) > invite.expires_at:
        flash("This invite has expired.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            invite.used_by = user.id
            invite.used_at = datetime.now(timezone.utc)
            db.session.commit()

            login_user(user)
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for("characters.character_list"))

    return render_template("auth/register.html", invite_token=token)


@auth_bp.route("/logout")
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))
