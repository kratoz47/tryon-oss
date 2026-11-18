import io
import os
import time

from PIL import Image


ENDPOINT = "fal-ai/nano-banana-2/edit"


class GenerationError(Exception):
    pass


def ready():
    return bool(os.environ.get("FAL_KEY", "").strip())


def _generate(person, reference, prompt):
    import fal_client
    import httpx

    references = reference if isinstance(reference, list) else [reference]
    urls = []
    for image in [person, *references]:
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=90)
        urls.append(fal_client.upload(buffer.getvalue(), "image/jpeg"))
    try:
        handle = fal_client.submit(ENDPOINT, arguments={
            "prompt": prompt, "image_urls": urls, "aspect_ratio": "2:3",
            "num_images": 1, "resolution": "1K", "output_format": "jpeg",
        })
        deadline = time.monotonic() + 240
        while not isinstance(handle.status(), fal_client.Completed):
            if time.monotonic() >= deadline:
                raise GenerationError("fal.ai 任务仍在处理中，请稍后查询结果。")
            time.sleep(2)
        result = handle.get()
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status in (401, 403):
            raise GenerationError("fal.ai 授权失败，请检查服务端密钥权限。") from None
        if status == 402:
            raise GenerationError("fal.ai 账户余额不足。") from None
        raise GenerationError("fal.ai 暂时无法完成生成，请稍后重试。") from None
    images = result.get("images") or []
    if not images or result.get("has_nsfw_concepts", [False])[0]:
        raise GenerationError("fal.ai 未返回可用图片，请更换参考照片。")
    url = images[0].get("url", "")
    if not url.startswith("https://"):
        raise GenerationError("fal.ai 返回的图片地址无效。")
    with httpx.stream("GET", url, timeout=30, follow_redirects=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 30_000_000:
                raise GenerationError("生成图过大，请重试。")
    with Image.open(io.BytesIO(data)) as image:
        image.thumbnail((1024, 1536))
        return image.convert("RGB")



def generate(person, reference, prompt):
    import httpx
    import fal_client

    try:
        return _generate(person, reference, prompt)
    except httpx.HTTPStatusError as error:
        if "exhausted balance" in error.response.text.lower() or error.response.status_code == 402:
            raise GenerationError("fal.ai 账户余额不足，暂时无法生成。") from None
        if error.response.status_code in (401, 403):
            raise GenerationError("fal.ai 授权失败，请检查服务端密钥权限。") from None
        raise GenerationError("fal.ai 请求失败，请稍后重试。") from None
    except fal_client.FalClientError:
        raise GenerationError("fal.ai 任务未能完成，请检查账户状态或更换参考照片。") from None
