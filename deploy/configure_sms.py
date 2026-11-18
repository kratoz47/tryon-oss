"""Run interactively on the server; never paste access secrets into chat."""
import datetime
import getpass
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess


def quote(value):
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise ValueError("值不能为空或包含换行。")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise SystemExit("请在服务器使用 sudo 运行。")
    target = Path("/etc/tryon/tryon.env")
    if target.is_symlink() or not target.is_file():
        raise SystemExit("没有找到原有服务配置，停止修改。")
    database = Path("/var/lib/tryon/accounts.sqlite3")
    if database.exists():
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
            pending = db.execute("SELECT COUNT(*) FROM avatar_jobs WHERE status='pending'").fetchone()[0]
        if pending:
            raise SystemExit("仍有分身正在生成，请完成后再配置并重启。")
    print("请先确认资质、签名、验证码模板审核与运营商报备已完成。")
    sign = input("短信签名名称：").strip()
    template = input("验证码模板 CODE（SMS_ 开头）：").strip()
    if not re.fullmatch(r"SMS_[A-Za-z0-9]+", template):
        raise SystemExit("模板 CODE 格式不正确。")
    key_id = getpass.getpass("RAM AccessKey ID（隐藏输入）：").strip()
    secret = getpass.getpass("RAM AccessKey Secret（隐藏输入）：").strip()
    values = {"SHIYI_SMS_SIGN_NAME": sign, "SHIYI_SMS_TEMPLATE_CODE": template,
              "ALIBABA_CLOUD_ACCESS_KEY_ID": key_id, "ALIBABA_CLOUD_ACCESS_KEY_SECRET": secret}
    additions = [name + "=" + quote(value) for name, value in values.items()]
    existing = target.read_text(encoding="utf-8").splitlines()
    preserved = [line for line in existing if line.split("=", 1)[0] not in values]
    backup = target.with_name("shiyi.env.before-sms-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(target, backup)
    backup.chmod(0o600)
    temporary = target.with_name("shiyi.env.new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("\n".join(preserved + additions) + "\n")
    temporary.replace(target)
    subprocess.run(["systemctl", "restart", "shiyi"], check=True)
    print("短信配置已保存。没有发送测试短信，请在网页中用自己的手机号验证。")


if __name__ == "__main__":
    main()
