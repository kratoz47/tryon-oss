"""Private phone accounts, avatar library and transactional free-generation ledger."""
import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time


class AccountError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalize_phone(value):
    if not isinstance(value, str):
        raise AccountError("请输入中国大陆手机号。")
    phone = re.sub(r"[\s-]", "", value)
    if phone.startswith("+86"):
        phone = phone[3:]
    if not re.fullmatch(r"1[3-9]\d{9}", phone):
        raise AccountError("请输入有效的中国大陆手机号。")
    return phone


class UserStore:
    FREE_AVATARS = None

    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.images = self.directory / "avatars"
        self.images.mkdir(exist_ok=True, mode=0o700)
        secret_path = self.directory / "auth.secret"
        try:
            fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(secrets.token_bytes(32))
        self.secret = secret_path.read_bytes()
        if len(self.secret) != 32:
            raise RuntimeError("Invalid authentication secret")
        self.database = self.directory / "accounts.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY, phone_key TEXT UNIQUE NOT NULL,
                  phone_masked TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                  expires REAL NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS otp (
                  phone_key TEXT PRIMARY KEY, challenge TEXT NOT NULL, code_hash TEXT NOT NULL,
                  expires REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS sms_events (
                  phone_key TEXT NOT NULL, ip_key TEXT NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS sms_time ON sms_events(created);
                CREATE TABLE IF NOT EXISTS avatar_jobs (
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                  request_key TEXT NOT NULL, token TEXT NOT NULL, status TEXT NOT NULL,
                  settings TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                  error TEXT, UNIQUE(user_id, request_key));
                CREATE TABLE IF NOT EXISTS avatars (
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                  kind TEXT NOT NULL, settings TEXT NOT NULL, created REAL NOT NULL,
                  deleted INTEGER NOT NULL DEFAULT 0);
            """)
            # A killed process cannot produce a result; release its reserved free slot.
            db.execute("UPDATE avatar_jobs SET status='failed', error=?, updated=? WHERE status='pending'",
                       ("服务已重启，请检查结果后重新生成。", time.time()))
        os.chmod(self.database, 0o600)

    @contextmanager
    def connection(self, transaction=False):
        db = sqlite3.connect(self.database, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if transaction:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if transaction:
                db.execute("COMMIT")
        except Exception:
            if transaction and db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def digest(self, purpose, value):
        return hmac.new(self.secret, (purpose + ":" + value).encode(), hashlib.sha256).hexdigest()

    def send_code(self, phone, ip, sender):
        phone = normalize_phone(phone)
        key, ip_key, now = self.digest("phone", phone), self.digest("ip", ip), time.time()
        challenge, code = secrets.token_hex(16), f"{secrets.randbelow(1000000):06d}"
        with self.connection(True) as db:
            db.execute("DELETE FROM sms_events WHERE created < ?", (now - 86400,))
            counts = db.execute("SELECT COUNT(*) AS day, SUM(created>?) AS hour, MAX(created) AS last FROM sms_events WHERE phone_key=?",
                                (now - 3600, key)).fetchone()
            ip_count = db.execute("SELECT COUNT(*) FROM sms_events WHERE ip_key=? AND created>?", (ip_key, now - 3600)).fetchone()[0]
            total = db.execute("SELECT COUNT(*) FROM sms_events").fetchone()[0]
            if ((counts["last"] and now - counts["last"] < 60) or counts["day"] >= 10 or
                    (counts["hour"] or 0) >= 5 or ip_count >= 20 or total >= 100):
                raise AccountError("验证码发送过于频繁，请稍后再试。", 429)
            db.execute("INSERT INTO sms_events VALUES(?,?,?)", (key, ip_key, now))
            db.execute("INSERT OR REPLACE INTO otp VALUES(?,?,?,?,0)",
                       (key, challenge, self.digest("otp", key + challenge + code), now + 300))
        try:
            sender(phone, code)
        except Exception:
            with self.connection(True) as db:
                db.execute("DELETE FROM otp WHERE phone_key=? AND challenge=?", (key, challenge))
            raise
        return {"sent": True, "retry_after": 60, "expires_in": 300}

    def verify_code(self, phone, code):
        phone = normalize_phone(phone)
        if not isinstance(code, str) or not re.fullmatch(r"\d{6}", code):
            raise AccountError("请输入 6 位验证码。")
        key, now, failure = self.digest("phone", phone), time.time(), False
        with self.connection(True) as db:
            row = db.execute("SELECT * FROM otp WHERE phone_key=?", (key,)).fetchone()
            if not row or row["expires"] < now or row["attempts"] >= 5:
                failure = True
            elif not hmac.compare_digest(row["code_hash"], self.digest("otp", key + row["challenge"] + code)):
                db.execute("UPDATE otp SET attempts=attempts+1 WHERE phone_key=?", (key,))
                failure = True
            else:
                db.execute("DELETE FROM otp WHERE phone_key=?", (key,))
                user = db.execute("SELECT * FROM users WHERE phone_key=?", (key,)).fetchone()
                if user is None:
                    user_id = secrets.token_hex(16)
                    db.execute("INSERT INTO users VALUES(?,?,?,?)", (user_id, key, phone[:3] + "****" + phone[-4:], now))
                    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                token = secrets.token_urlsafe(32)
                db.execute("DELETE FROM sessions WHERE expires<?", (now,))
                db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (self.digest("session", token), user["id"], now + 30 * 86400, now))
                result = {"id": user["id"], "phone_masked": user["phone_masked"]}
        if failure:
            raise AccountError("验证码错误或已过期，请重新确认。")
        return result, token

    def session(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 100:
            return None
        with self.connection() as db:
            row = db.execute("SELECT u.id,u.phone_masked FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?",
                             (self.digest("session", token), time.time())).fetchone()
            return {**dict(row), "guest": row["phone_masked"] == "当前浏览器"} if row else None

    def create_guest(self):
        now = time.time()
        user_id, token = secrets.token_hex(16), secrets.token_urlsafe(32)
        with self.connection(True) as db:
            db.execute("INSERT INTO users VALUES(?,?,?,?)", (user_id, "guest:" + user_id, "当前浏览器", now))
            db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (self.digest("session", token), user_id, now + 365 * 86400, now))
        return {"id": user_id, "phone_masked": "当前浏览器", "guest": True}, token

    def logout(self, token):
        if token:
            with self.connection(True) as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (self.digest("session", token),))

    def quota(self, user_id):
        with self.connection() as db:
            return self._quota(db, user_id)

    def _quota(self, db, user_id):
        rows = db.execute("SELECT status,COUNT(*) n FROM avatar_jobs WHERE user_id=? GROUP BY status", (user_id,)).fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        used, reserved = counts.get("completed", 0), counts.get("pending", 0)
        return {"limit": None, "used": used, "reserved": reserved,
                "remaining": None, "unlimited": True}

    def existing_job(self, user_id, request_key):
        with self.connection() as db:
            row = db.execute("SELECT * FROM avatar_jobs WHERE user_id=? AND request_key=?", (user_id, request_key)).fetchone()
            return {**dict(row), "guest": row["phone_masked"] == "当前浏览器"} if row else None

    def reserve_avatar(self, user_id, request_key, settings, job_id, token):
        if not isinstance(request_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", request_key):
            raise AccountError("生成请求标识无效，请刷新后重试。")
        with self.connection(True) as db:
            old = db.execute("SELECT * FROM avatar_jobs WHERE user_id=? AND request_key=?", (user_id, request_key)).fetchone()
            if old:
                return dict(old), False
            now = time.time()
            db.execute("INSERT INTO avatar_jobs(id,user_id,request_key,token,status,settings,created,updated) VALUES(?,?,?,?,?,?,?,?)",
                       (job_id, user_id, request_key, token, "pending", json.dumps(settings, ensure_ascii=False), now, now))
            return dict(db.execute("SELECT * FROM avatar_jobs WHERE id=?", (job_id,)).fetchone()), True

    def fail_avatar(self, job_id, error):
        with self.connection(True) as db:
            db.execute("UPDATE avatar_jobs SET status='failed',error=?,updated=? WHERE id=? AND status='pending'", (error, time.time(), job_id))

    def finish_avatar(self, job_id, image_bytes):
        with self.connection(True) as db:
            row = db.execute("SELECT * FROM avatar_jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["status"] != "pending":
                raise AccountError("分身任务已结束，请刷新分身库。")
            self._write_image(job_id, image_bytes)
            db.execute("INSERT INTO avatars VALUES(?,?,?,?,?,0)", (job_id, row["user_id"], "generated", row["settings"], time.time()))
            db.execute("UPDATE avatar_jobs SET status='completed',updated=? WHERE id=?", (time.time(), job_id))
        return job_id

    def _write_image(self, avatar_id, image_bytes):
        if not re.fullmatch(r"[a-f0-9]{32}", avatar_id) or not 0 < len(image_bytes) <= 10_000_000:
            raise AccountError("分身图片无法保存。")
        path = self.images / (avatar_id + ".jpg")
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(image_bytes)
        temporary.chmod(0o600)
        temporary.replace(path)

    def save_uploaded(self, user_id, image_bytes):
        with self.connection(True) as db:
            n = db.execute("SELECT COUNT(*) FROM avatars WHERE user_id=? AND kind='photo' AND deleted=0", (user_id,)).fetchone()[0]
            if n >= 8:
                raise AccountError("上传照片分身最多保留 8 张，请先移除不需要的照片。", 409)
            avatar_id = secrets.token_hex(16)
            self._write_image(avatar_id, image_bytes)
            db.execute("INSERT INTO avatars VALUES(?,?,?,?,?,0)", (avatar_id, user_id, "photo", "null", time.time()))
        return avatar_id

    def avatars(self, user_id):
        with self.connection() as db:
            rows = db.execute("SELECT id,kind,settings,created FROM avatars WHERE user_id=? AND deleted=0 ORDER BY created DESC", (user_id,)).fetchall()
        return [{"id": r["id"], "kind": r["kind"], "settings": json.loads(r["settings"]),
                 "created": r["created"], "image_url": "/api/avatars/" + r["id"] + "/image"} for r in rows]

    def image(self, user_id, avatar_id):
        if not isinstance(avatar_id, str) or not re.fullmatch(r"[a-f0-9]{32}", avatar_id):
            raise AccountError("分身不存在。", 404)
        with self.connection() as db:
            row = db.execute("SELECT 1 FROM avatars WHERE id=? AND user_id=? AND deleted=0", (avatar_id, user_id)).fetchone()
        path = self.images / (avatar_id + ".jpg")
        if not row or not path.is_file():
            raise AccountError("分身不存在。", 404)
        return path.read_bytes()

    def delete_avatar(self, user_id, avatar_id):
        self.image(user_id, avatar_id)
        with self.connection(True) as db:
            db.execute("UPDATE avatars SET deleted=1 WHERE id=? AND user_id=?", (avatar_id, user_id))
        (self.images / (avatar_id + ".jpg")).unlink(missing_ok=True)

    def poll_avatar(self, user_id, job_id, token):
        with self.connection() as db:
            row = db.execute("SELECT * FROM avatar_jobs WHERE id=? AND user_id=?", (job_id, user_id)).fetchone()
        if not row or not isinstance(token, str) or not hmac.compare_digest(row["token"], token):
            return None
        result = {"status": row["status"], "settings": json.loads(row["settings"])}
        if row["status"] == "completed":
            try:
                data = self.image(user_id, job_id)
            except AccountError:
                return {"status": "failed", "error": "该分身已被移除。"}
            result.update(avatar_id=job_id, image="data:image/jpeg;base64," + base64.b64encode(data).decode())
        elif row["status"] == "failed":
            result["error"] = row["error"] or "本次生成失败。"
        return result
