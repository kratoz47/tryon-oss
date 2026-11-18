"""Aliyun's official SMS SDK. No development code or bypass is exposed."""
import importlib.util
import json
import os


class SmsUnavailable(Exception):
    pass


def configured():
    names = ("ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
             "SHIYI_SMS_SIGN_NAME", "SHIYI_SMS_TEMPLATE_CODE")
    return all(os.environ.get(name, "").strip() for name in names) and bool(
        importlib.util.find_spec("alibabacloud_dysmsapi20170525"))


def send_login_code(phone, code):
    if not configured():
        raise SmsUnavailable("验证码服务尚未开通，请稍后再试。")
    from alibabacloud_dysmsapi20170525.client import Client
    from alibabacloud_dysmsapi20170525 import models as sms_models
    from alibabacloud_tea_openapi import models as api_models
    from alibabacloud_tea_util import models as util_models

    config = api_models.Config(
        access_key_id=os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"].strip(),
        access_key_secret=os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"].strip())
    config.endpoint = "dysmsapi.aliyuncs.com"
    config.protocol = "https"
    client = Client(config)
    request = sms_models.SendSmsRequest(
        phone_numbers=phone, sign_name=os.environ["SHIYI_SMS_SIGN_NAME"].strip(),
        template_code=os.environ["SHIYI_SMS_TEMPLATE_CODE"].strip(),
        template_param=json.dumps({"code": code}))
    runtime = util_models.RuntimeOptions(connect_timeout=5000, read_timeout=10000, autoretry=False)
    try:
        response = client.send_sms_with_options(request, runtime)
        if response.body.code != "OK":
            raise SmsUnavailable("验证码发送失败，请稍后重试。")
    except SmsUnavailable:
        raise
    except Exception:
        # SDK exceptions may include phone numbers and request parameters.
        raise SmsUnavailable("验证码发送暂时不可用，请稍后重试。") from None
