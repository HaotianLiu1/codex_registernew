"""
mail.tm 临时邮箱封装。

通过 mail.tm 公共 API（https://api.mail.tm）自动创建临时邮箱、
获取鉴权 token 并轮询邮件中的 6 位验证码，无需任何预先配置。

用法示例:
    import mailtm
    proxies = {"http": "socks5://...", "https": "socks5://..."}  # 或 None
    account = mailtm.setup_mail_tm(proxies=proxies)
    code = account.fetch_code()   # 返回验证码字符串或 None
"""

import logging
import random
import re
import string
from dataclasses import dataclass, field
from typing import Optional

import requests

log = logging.getLogger("api_reg")

MAILTM_BASE = "https://api.mail.tm"
_DEFAULT_TIMEOUT = 20  # 秒


# ──────────────────────────────────────────────
# 验证码提取（与原 mailapi.py 逻辑一致）
# ──────────────────────────────────────────────

def _extract_code(text: str) -> Optional[str]:
    """从邮件文本中提取 6 位 OTP 验证码。

    匹配优先级：
    1. 精准上下文匹配（"code is 123456" / "Code: 123456" 等）
    2. 宽泛上下文匹配（"chatgpt/openai/verification" 前后 30 字符内）
    3. 兜底匹配（严格 6 位数字，排除 HTML 颜色代码 #XXXXXX）
    """
    # 优先级 1：精准上下文匹配（"code is 123456" / "Code: 123456" 等）
    match = re.search(r"(?i)(?:code[\s:]*(?:is\s*)?)(\d{6})\b", text)
    if match:
        return match.group(1)

    # 优先级 2：宽泛上下文匹配（"chatgpt/openai/verification" 附近）
    match = re.search(
        r"(?i)(?:chatgpt|openai|verification)[\s\S]{0,30}?\b(\d{6})\b", text
    )
    if match:
        return match.group(1)

    # 优先级 3：兜底匹配（排除 HTML 颜色代码 #XXXXXX）
    match = re.search(r"(?<!#)(?<!\d)\b\d{6}\b(?!\d)", text)
    if match:
        return match.group(0)

    return None


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

@dataclass
class MailTmAccount:
    """mail.tm 临时邮箱账号"""

    email: str
    _token: str = field(repr=False)
    _proxies: Optional[dict] = field(default=None, repr=False)
    # 已处理过的邮件 id 集合，防止重复提取同一封邮件的验证码
    _seen_ids: set = field(default_factory=set, repr=False)

    def fetch_code(self) -> Optional[str]:
        """
        查询收件箱，返回第一个尚未见过的 6 位验证码；
        未找到则返回 None。
        """
        try:
            messages = self._list_messages()
        except Exception as e:
            log.warning(f"    mail.tm 查询邮件列表失败: {e}")
            return None

        for msg in messages:
            mid = msg.get("id", "")
            if not mid or mid in self._seen_ids:
                continue

            # 获取完整邮件内容
            try:
                full = self._get_message(mid)
            except Exception as e:
                log.warning(f"    mail.tm 获取邮件 {mid[:8]}… 失败: {e}")
                continue

            self._seen_ids.add(mid)

            # 依次检查纯文本、HTML 正文与主题
            text_body = full.get("text", "") or ""
            html_body = full.get("html", "") or ""
            subject = full.get("subject", "") or ""

            # 先从纯文本提取，再尝试 HTML，最后看 subject
            for source in (text_body, html_body, subject):
                code = _extract_code(source)
                if code:
                    return code

        return None

    # ── 私有请求方法 ──

    def _list_messages(self) -> list:
        resp = requests.get(
            f"{MAILTM_BASE}/messages",
            headers={"Authorization": f"Bearer {self._token}"},
            proxies=self._proxies,
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("hydra:member", [])

    def _get_message(self, message_id: str) -> dict:
        resp = requests.get(
            f"{MAILTM_BASE}/messages/{message_id}",
            headers={"Authorization": f"Bearer {self._token}"},
            proxies=self._proxies,
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()


# ──────────────────────────────────────────────
# 公共工厂函数
# ──────────────────────────────────────────────

def _get_domain(proxies: Optional[dict]) -> str:
    """获取 mail.tm 上第一个可用的邮件域名"""
    resp = requests.get(
        f"{MAILTM_BASE}/domains",
        proxies=proxies,
        timeout=_DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    domains = resp.json().get("hydra:member", [])
    if not domains:
        raise RuntimeError("mail.tm 没有返回可用域名")
    return domains[0]["domain"]


def _random_local(length: int = 12) -> str:
    """生成随机邮箱本地部分"""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def setup_mail_tm(proxies: Optional[dict] = None) -> MailTmAccount:
    """
    通过 mail.tm API 创建一个全新的临时邮箱。

    参数:
        proxies: requests 格式代理字典，如
                 {"http": "socks5://ip:port", "https": "socks5://ip:port"}，
                 或 None 表示直连。

    返回:
        MailTmAccount 实例，包含 .email 属性与 .fetch_code() 方法。

    异常:
        RuntimeError / requests.HTTPError：账号创建或鉴权失败时抛出。
    """
    domain = _get_domain(proxies)
    address = f"{_random_local()}@{domain}"
    password = _random_local(16)

    # 1. 创建账号
    resp = requests.post(
        f"{MAILTM_BASE}/accounts",
        json={"address": address, "password": password},
        proxies=proxies,
        timeout=_DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()

    # 2. 获取 Bearer token
    resp = requests.post(
        f"{MAILTM_BASE}/token",
        json={"address": address, "password": password},
        proxies=proxies,
        timeout=_DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()

    token = resp.json().get("token", "")
    if not token:
        raise RuntimeError("mail.tm 返回的 token 为空")

    log.info(f"    📬 mail.tm 邮箱已创建: {address}")
    return MailTmAccount(email=address, _token=token, _proxies=proxies)
