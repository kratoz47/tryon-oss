import argparse
import base64
import binascii
import io
import json
import logging
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from PIL import Image

import agent_chat
import avatar_profile
import generation
import export_branding
import sms_provider
from user_store import UserStore, AccountError

ROOT = Path(__file__).resolve().parents[1]
SLOTS = {"上衣": "top", "下装": "bottoms", "鞋": "shoes",
         "帽子": "hat", "眼镜": "eyewear", "包": "bag"}
APPEARANCE = avatar_profile.APPEARANCE
IMAGE_LIMIT = 1_800_000
LIMIT = (len(SLOTS) + 1) * IMAGE_LIMIT + 4096
jobs = {}
lock = threading.Lock()
pipeline = None
weights = None
avatar_weights = None
flux_weights = None
origin = None
account_store = None
account_store_lock = threading.Lock()


def get_store():
    global account_store
    with account_store_lock:
        if account_store is None:
            account_store = UserStore(os.environ.get("SHIYI_DATA_DIR", str(ROOT / ".secrets" / "accounts")))
    return account_store


def decode_image(value):
    if not isinstance(value, str) or len(value) > IMAGE_LIMIT:
        raise ValueError("图片过大或格式无效。")
    prefix, _, data = value.partition(",")
    if prefix not in ("data:image/jpeg;base64", "data:image/png;base64"):
        raise ValueError("请使用 JPG 或 PNG 照片。")
    try:
        with Image.open(io.BytesIO(base64.b64decode(data, validate=True))) as source:
            if source.width * source.height > 4_000_000:
                raise ValueError("照片尺寸过大。")
            return source.convert("RGB")
    except (binascii.Error, OSError, Image.DecompressionBombError) as error:
        raise ValueError("无法读取照片。") from error


def run_job(job_id, person, garment=None, body=None, pose=None, appearance="preserve", profile=None, source="face", owner=None, provider="seedream"):
    try:
        started = time.monotonic()
        if garment is None:
            reference = []
            _, prompt, _ = avatar_profile.compile_prompt(
                profile if profile is not None else avatar_profile.from_legacy(body), appearance, pose, source)
        else:
            reference = [image for _, image in garment]
            mapping = ", ".join(f"image {i}: {SLOTS[slot]}" for i, (slot, _) in enumerate(garment, 2))
            prompt = (
                "Generate one realistic virtual try-on image. Use the first image as the person and replace "
                f"only the specified items using these exact references: {mapping}. Preserve the person's "
                "face, body shape, pose, framing, background and all unlisted clothing. Match colors, shapes and prints."
            )
        rendered = generation.generate(person, reference, prompt, provider)
        buffer = io.BytesIO()
        rendered.save(buffer, format="JPEG", quality=88)
        output = {"status": "completed", "provider": provider, "model": generation.model(provider), "image": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")}
        if garment is None and owner:
            output["avatar_id"] = get_store().finish_avatar(job_id, buffer.getvalue())
        logging.info("%s generation completed in %.1f seconds", provider, time.monotonic() - started)
    except Exception as error:
        logging.warning("%s generation failed: %s", provider, type(error).__name__)
        output = {"status": "failed", "error": str(error) if isinstance(error, generation.GenerationError) else "所选模型未能返回生成图，请稍后重试。"}
        if garment is None and owner:
            get_store().fail_avatar(job_id, output["error"])
    with lock:
        jobs[job_id].update(output, finished=time.monotonic())


class Server(BaseHTTPRequestHandler):
    def reply(self, status, body, mime="application/json; charset=utf-8", headers=None):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def session_token(self):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie["SHIYI_SID"].value if "SHIYI_SID" in cookie else None
        except CookieError:
            return None

    def user(self):
        return get_store().session(self.session_token())

    def require_user(self):
        user = self.user()
        if not user:
            raise AccountError("当前浏览器身份已失效，请刷新页面后重试。", 401)
        return user

    def account_payload(self, user):
        return {"user": user, "sms_ready": False, "login_required": False,
                "quota": get_store().quota(user["id"]) if user else None,
                "avatars": get_store().avatars(user["id"]) if user else []}

    def read_payload(self, limit):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= limit:
                raise ValueError()
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError()
            return payload
        except (ValueError, UnicodeError):
            raise AccountError("请求格式无效或内容过大。") from None

    def account_post(self):
        try:
            payload = self.read_payload(IMAGE_LIMIT + 4096 if self.path == "/api/avatars" else 8192)
            if self.path == "/api/auth/send-code":
                if payload.get("consent") is not True:
                    raise AccountError("请先确认手机号登录与分身保存说明。")
                if not sms_provider.configured():
                    raise AccountError("验证码登录暂未开通，请稍后再试。", 503)
                data = get_store().send_code(payload.get("phone"), self.headers.get("X-Real-IP", self.client_address[0]), sms_provider.send_login_code)
                self.reply(200, data)
            elif self.path == "/api/auth/verify":
                if payload.get("consent") is not True:
                    raise AccountError("请先确认手机号登录与分身保存说明。")
                user, token = get_store().verify_code(payload.get("phone"), payload.get("code"))
                secure = "; Secure" if urlsplit(origin).scheme == "https" else ""
                self.reply(200, self.account_payload(user), headers={"Set-Cookie": "SHIYI_SID=" + token + "; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000" + secure})
            elif self.path == "/api/auth/logout":
                get_store().logout(self.session_token())
                self.reply(200, {"ok": True}, headers={"Set-Cookie": "SHIYI_SID=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"})
            elif self.path == "/api/avatars":
                user = self.require_user()
                image = decode_image(payload.get("image"))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=88)
                avatar_id = get_store().save_uploaded(user["id"], buffer.getvalue())
                self.reply(201, {"avatar_id": avatar_id, **self.account_payload(user)})
            elif self.path == "/api/avatars/delete":
                user = self.require_user()
                get_store().delete_avatar(user["id"], payload.get("id"))
                self.reply(200, self.account_payload(user))
        except AccountError as error:
            self.reply(error.status, {"error": str(error)})
        except ValueError as error:
            self.reply(400, {"error": str(error)})
        except sms_provider.SmsUnavailable as error:
            self.reply(503, {"error": str(error)})

    def valid_host(self):
        if self.headers.get("Host") == urlsplit(origin).netloc:
            return True
        self.reply(403, {"error": "无效的本机地址。"})
        return False

    def do_GET(self):
        if not self.valid_host():
            return
        url = urlsplit(self.path)
        if url.path == "/":
            html = (ROOT / "web" / "index.html").read_text(encoding="utf-8-sig")
            html = html.replace("本次试穿会将人物照和上衣图发给 FASHN 生成。", "本次试穿会把人物照和上衣图上传至 火山方舟 Seedream，可能消耗积分。")
            self.reply(200, html.encode(), "text/html; charset=utf-8")
        elif url.path == "/avatar.svg":
            self.reply(200, (ROOT / "web" / "avatar.svg").read_bytes(), "image/svg+xml")
        elif url.path == "/agent-chat.js":
            self.reply(200, (ROOT / "web" / "agent-chat.js").read_bytes(), "application/javascript; charset=utf-8")
        elif url.path == "/api/agent/status":
            self.reply(200, agent_chat.status())
        elif url.path == "/account-export.js":
            self.reply(200, (ROOT / "web" / "account-export.js").read_bytes(), "application/javascript; charset=utf-8")
        elif url.path in ("/assets/avatar-reference.jpg", "/assets/closet-reference.jpg"):
            self.reply(200, (ROOT / "web" / url.path.lstrip("/")).read_bytes(), "image/jpeg")
        elif url.path == "/body-lab" or url.path.startswith("/body-lab/"):
            self.reply(410, {"error": "白模实验入口已停用，请在分身创建中选择身形描述。"})
        elif url.path == "/api/avatar/options":
            self.reply(200, generation.options())
        elif url.path == "/api/me":
            user = self.user()
            headers = None
            if not user:
                user, token = get_store().create_guest()
                secure = "; Secure" if urlsplit(origin).scheme == "https" else ""
                headers = {"Set-Cookie": "SHIYI_SID=" + token + "; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000" + secure}
            self.reply(200, self.account_payload(user), headers=headers)
        elif url.path == "/api/export/config":
            self.reply(200, export_branding.config())
        elif url.path == "/api/export/qr.png":
            code = export_branding.qr_png()
            if code:
                self.reply(200, code, "image/png")
            else:
                self.reply(404, {"error": "APP 下载地址尚未设置。"})
        elif re.fullmatch(r"/api/avatars/[a-f0-9]{32}/image", url.path):
            try:
                user = self.require_user()
                self.reply(200, get_store().image(user["id"], url.path.split("/")[3]), "image/jpeg")
            except AccountError as error:
                self.reply(error.status, {"error": str(error)})
        elif url.path == "/api/avatar/config":
            self.reply(200, avatar_profile.public_config())
        elif url.path == "/api/avatar/pose":
            self.reply(410, {"error": "站姿现通过描述设置，不再使用白模参考图。"})
        elif url.path in ("/api/try-on", "/api/avatar"):
            params = parse_qs(url.query)
            user = self.user()
            if url.path == "/api/avatar":
                if not user:
                    self.reply(401, {"error": "请登录后查看分身。"})
                    return
                result = get_store().poll_avatar(user["id"], params.get("id", [""])[0], params.get("token", [""])[0])
                self.reply(200, result or {"status": "failed", "error": "任务不存在或无权访问。"})
                return
            with lock:
                job = jobs.get(params.get("id", [""])[0])
                if job and (not job.get("owner") or user and user["id"] == job["owner"]) and secrets.compare_digest(job["token"], params.get("token", [""])[0]):
                    result = {key: value for key, value in job.items() if key in ("status", "image", "error", "settings")}
                else:
                    result = None
            if result is None:
                self.reply(200, {"status": "failed", "error": "任务已过期或服务已重启，请重新生成。"})
            else:
                self.reply(200, result)
        else:
            self.reply(404, {"error": "页面不存在。"})

    def do_POST(self):
        if not self.valid_host():
            return
        account_routes = ("/api/auth/send-code", "/api/auth/verify", "/api/auth/logout", "/api/avatars", "/api/avatars/delete")
        if self.path not in ("/api/try-on", "/api/avatar", "/api/agent/chat", *account_routes):
            self.reply(404, {"error": "接口不存在。"})
            return
        if self.headers.get("Origin") != origin:
            self.reply(403, {"error": "仅允许本机试衣间提交任务。"})
            return
        if self.path == "/api/agent/chat":
            try:
                self.require_user()
                self.reply(200, agent_chat.respond(self.read_payload(100000)))
            except AccountError as error:
                self.reply(error.status, {"error": str(error)})
            except agent_chat.ChatError as error:
                self.reply(400, {"error": str(error)})
            return
        if self.path.startswith("/api/auth/"):
            self.reply(410, {"error": "短信登录已取消，请直接使用。"})
            return
        if self.path in account_routes:
            self.account_post()
            return
        is_avatar = self.path == "/api/avatar"
        user = self.user()
        if is_avatar and not user:
            self.reply(401, {"error": "请先刷新页面以建立浏览器身份。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= LIMIT:
                raise ValueError("照片太大或请求为空。")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("请求格式无效。")
            provider = generation.validate(payload.get("provider", generation.DEFAULT_PROVIDER))
            request_key = payload.get("request_key")
            if is_avatar:
                if not isinstance(request_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", request_key):
                    raise ValueError("生成请求标识无效，请刷新后重试。")
                old = get_store().existing_job(user["id"], request_key)
                if old:
                    self.reply(202, {"id": old["id"], "token": old["token"], "settings": json.loads(old["settings"])})
                    return
            person = decode_image(payload.get("person"))
            body, pose = payload.get("body"), payload.get("pose")
            appearance = payload.get("appearance", "preserve")
            source = payload.get("source", "face") if is_avatar else "face"
            profile, settings = None, None
            if is_avatar and (not isinstance(appearance, str) or appearance not in APPEARANCE):
                raise ValueError("请选择有效的分身外观。")
            if is_avatar:
                if "prompt_version" in payload and payload["prompt_version"] != avatar_profile.PROMPT_VERSION:
                    raise ValueError("身形描述方案已更新，请刷新页面后再生成。")
                if not isinstance(pose, str) or pose not in avatar_profile.POSE or not isinstance(source, str) or source not in ("face", "full"):
                    raise ValueError("请选择有效的照片方式与站姿。")
                if "profile" in payload:
                    profile = avatar_profile.validate(payload["profile"], source)
                else:
                    if not isinstance(body, str):
                        raise ValueError("请选择身形。")
                    profile = avatar_profile.from_legacy(body)
                _, _, fingerprint = avatar_profile.compile_prompt(profile, appearance, pose, source)
                settings = {"provider": provider, "model": generation.model(provider), "profile": profile, "appearance": appearance, "pose": pose, "source": source,
                            "prompt_version": avatar_profile.PROMPT_VERSION, "prompt_fingerprint": fingerprint}
            garment = None
            if not is_avatar:
                entries = payload.get("garments")
                if entries is None and payload.get("garment"):
                    entries = [{"category": "上衣", "image": payload["garment"]}]
                if not isinstance(entries, list) or not 1 <= len(entries) <= len(SLOTS):
                    raise ValueError(f"请选择 1 至 {len(SLOTS)} 件单品。")
                garment = []
                for entry in entries:
                    if not isinstance(entry, dict) or not isinstance(entry.get("category"), str) or entry["category"] not in SLOTS:
                        raise ValueError("单品类别无效。")
                    garment.append((entry["category"], decode_image(entry.get("image"))))
                if len({category for category, _ in garment}) != len(garment):
                    raise ValueError("每个槽位只能选择一件单品。")
        except (ValueError, UnicodeError) as error:
            self.reply(400, {"error": str(error)})
            return
        if not generation.ready(provider):
            self.reply(503, {"error": "所选模型的服务端密钥尚未配置，请切换模型。"})
            return
        try:
            with lock:
                if any(job["status"] == "pending" for job in jobs.values()):
                    job_id = None
                else:
                    expired = [key for key, job in jobs.items() if time.monotonic() - job["finished"] > 3600]
                    for key in expired:
                        del jobs[key]
                    while len(jobs) >= 10:
                        del jobs[next(iter(jobs))]
                    job_id, token = secrets.token_hex(16), secrets.token_hex(24)
                    if is_avatar:
                        reserved, created = get_store().reserve_avatar(user["id"], request_key, settings, job_id, token)
                        if not created:
                            self.reply(202, {"id": reserved["id"], "token": reserved["token"], "settings": json.loads(reserved["settings"])})
                            return
                    jobs[job_id] = {"provider": provider, "model": generation.model(provider), "status": "pending", "token": token, "owner": user["id"] if user else None}
                    if settings is not None:
                        jobs[job_id]["settings"] = settings
        except AccountError as error:
            self.reply(error.status, {"error": str(error)})
            return
        if job_id is None:
            self.reply(429, {"error": "本机正在试穿，请等待当前任务完成。"})
            return
        try:
            threading.Thread(target=run_job, args=(job_id, person, garment, body, pose, appearance if is_avatar else "preserve", profile, source, user["id"] if user else None, provider), daemon=True).start()
        except RuntimeError:
            error = "生成服务正忙，请稍后重试。"
            if is_avatar:
                get_store().fail_avatar(job_id, error)
            with lock:
                jobs[job_id].update(status="failed", error=error, finished=time.monotonic())
            self.reply(503, {"error": error})
            return
        response = {"id": job_id, "token": token, "provider": provider, "model": generation.model(provider)}
        if settings is not None:
            response["settings"] = settings
        self.reply(202, response)

    def log_message(self, format, *args):
        # Query strings contain task tokens.
        logging.info("%s %s", self.command, urlsplit(self.path).path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--avatar-weights", type=Path)
    parser.add_argument("--flux-weights", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    options = parser.parse_args()
    weights = options.weights.resolve() if options.weights else None
    avatar_weights = options.avatar_weights.resolve() if options.avatar_weights else None
    flux_weights = options.flux_weights.resolve() if options.flux_weights else None
    origin = os.environ.get("APP_ORIGIN", f"http://127.0.0.1:{options.port}").rstrip("/")
    parsed_origin = urlsplit(origin)
    if parsed_origin.scheme not in ("http", "https") or not parsed_origin.netloc or parsed_origin.path:
        parser.error("APP_ORIGIN must contain only scheme and host")
    logging.basicConfig(level=logging.INFO)
    get_store()
    with ThreadingHTTPServer(("127.0.0.1", options.port), Server) as server:
        logging.info("Local fitting room at %s", origin)
        server.serve_forever()



