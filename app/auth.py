import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request

from . import db

COOKIE = "bss_session"
SESSION_DAYS = 30


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except ValueError:
        return False


def new_session(con, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    exp = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, user_id, exp))
    con.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
    return token


def current_user(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Please sign in.")
    with db.connect() as c:
        u = db.row(c, """SELECT u.id,u.email,u.name,u.role,u.active FROM sessions s JOIN users u ON u.id=s.user_id
                         WHERE s.token=? AND s.expires_at > ?""", token, datetime.now(timezone.utc).isoformat())
    if not u or not u["active"]:
        raise HTTPException(401, "Please sign in.")
    return u


def require_admin(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Only admins can do this.")
    return u
