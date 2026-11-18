"""Server-only Seedream adapter. Never retries ambiguous paid submissions."""
import base64
import binascii
import io
import json
import os
import socket
import urllib.error
import urllib.request
from PIL import Image

ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
DEFAULT_MODEL = "doubao-seedream-5-0-flash-260915"
MAX_RESPONSE = 40_000_000

class GenerationError(Exception):
    pass

def ready():
    return bool(os.environ.get("ARK_API_KEY", "").strip())

def model():
    return os.environ.get("ARK_IMAGE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

def generate(person, reference, prompt):
    if not ready():
        raise GenerationError("火山方舟服务端密钥尚未配置。")
    references = reference if isinstance(reference, list) else [reference]
    images = []
    for image in [person, *references]:
        if image is None:
            continue
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "JPEG", quality=90)
        images.append("data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"))
    if not 1 <= len(images) <= 14:
        raise GenerationError("参考图片数量无效。")
    payload = {"model": model(), "prompt": prompt, "image": images,
               "size": "1664x2496", "output_format": "jpeg", "response_format": "b64_json",
               "watermark": True}
    request = urllib.request.Request(ENDPOINT, json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + os.environ["ARK_API_KEY"].strip(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise GenerationError("生成结果过大，请联系管理员。")
        result = json.loads(raw)
        entries = result.get("data") or []
        encoded = entries[0].get("b64_json") if entries else None
        if not isinstance(encoded, str) or not encoded:
            raise GenerationError("火山方舟未返回可用图片，请检查参考照片。")
        data = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 20_000_000:
                raise GenerationError("生成图片尺寸过大。")
            image.thumbnail((1024, 1536))
            return image.convert("RGB")
    except urllib.error.HTTPError as error:
        messages = {401: "火山方舟密钥无效，请检查服务端配置。", 403: "火山方舟模型未开通或密钥无权访问。",
                    404: "火山方舟模型不可用，请检查模型开通状态与模型 ID。",
                    429: "火山方舟请求限流或额度不足，请稍后再试。", 400: "火山方舟拒绝了生成参数或参考图片。"}
        raise GenerationError(messages.get(error.code, "火山方舟生成失败，请稍后查询任务状态。")) from None
    except (TimeoutError, socket.timeout, urllib.error.URLError):
        raise GenerationError("连接火山方舟超时或中断，上游可能仍在处理；请勿立即重复生成。") from None
    except (ValueError, KeyError, TypeError, OSError, binascii.Error):
        raise GenerationError("无法读取火山方舟返回的图片。") from None
