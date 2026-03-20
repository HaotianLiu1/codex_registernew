# codex-register-py

基于 Python 的 HTTP 自动化脚本，通过接口执行账号注册/登录相关步骤，并通过 **mail.tm** 临时邮箱自动获取 OTP 验证码，注册完成后自动上传到CPA（如果有配置的话）。
项目参考：https://github.com/Ethan-W20/openai-auto-register

本项目依旧可用，如无法注册请自行检查代理质量

## 免责声明

请仅在你有明确授权、并且符合目标平台条款与当地法律法规的前提下使用本项目。由不当使用产生的风险与责任由使用者自行承担。项目仅供参考学习，请勿滥用！！！本项目不对任何因使用、误用或滥用而导致的账号封禁、法律责任或其他损失承担任何责任。

## 项目结构

```text
codex_register.py      # 主流程：并发执行、验证码轮询、结果保存、上传
mailtm.py            # mail.tm 临时邮箱封装：创建邮箱、获取 token、拉取验证码
mailapi.py           # 原 MailAPI 封装（已废弃，保留备用）
proxy_cache.json     # 代理缓存（可选）
tokens/              # 生成结果目录（自动创建）
requirements.txt     # Python 依赖列表
README.md
```

## 运行环境

- Python 3.10+
- Windows / Linux / macOS

## 安装依赖

使用 `requirements.txt` 一键安装：

```bash
pip install -r requirements.txt
```

等价依赖为：`curl_cffi`、`requests`、`PySocks`。

说明：
- `curl_cffi`：主注册流程 HTTP 会话及浏览器指纹模拟。
- `requests`：mail.tm 邮箱 API 调用与上传逻辑。
- `pysocks`：`requests` 使用 socks4/socks5 代理时需要。

## 配置说明

在 `codex_register.py` 中配置以下常量（均为可选）：

```python
CPA_URL = "http://your-server:port"
MANAGEMENT_KEY = "your-management-key"
```

字段说明：
- `CPA_URL` / `MANAGEMENT_KEY`：token 文件上传的CPA服务地址和登陆密钥（可选，不配置则只保存本地）。

> **mail.tm 自动邮箱**：不再需要配置 `MAIL_API_URL`、`MAIL_API_AUTH`、`EMAIL_DOMAINS` 等 MailAPI 相关参数。脚本会自动调用 [mail.tm](https://mail.tm) 公共 API 为每次注册创建一次性临时邮箱，并自动拉取 OTP 验证码。

## 使用方式

在项目目录执行：

```bash
python codex_register.py
```

参数：
- `--count`：本次处理数量，默认 `5`。
- `--workers`：并发线程数，默认 `1`。

示例：

```bash
python codex_register.py --count 1 --workers 1
python codex_register.py --count 20 --workers 5
```
<img width="889" height="482" alt="image" src="https://github.com/user-attachments/assets/323147d4-65d1-4cfd-8d9b-b5fcaee6f010" />

`本地网络太差了，请求一个网址要好久，如果部署再云端的话会快不少，单线程平均1-3s一个账号`

## 运行流程（按当前代码）

1. 从 `proxy_cache.json` 读取可用代理（若为空则直连）。
2. 调用 mail.tm API 自动创建临时邮箱。
3. 执行 OAuth/OTP/账号信息提交流程。
4. 通过 mail.tm 收件箱轮询验证码并校验。
5. 将结果保存到 `tokens/*.json`。
6. 若成功条目大于 0 且配置了 `CPA_URL`，则调用上传接口并在上传成功后删除本地文件。

## 输出说明

- 日志文件：`codex_register.log`
- token 结果：`tokens/<email>--<password>.json`
- 统计输出：成功数、失败数、总耗时

## 代理池说明

`codex_register.py` 只负责读取 `proxy_cache.json` 并随机使用。

缓存规则（按当前代码）：
- 以 UTC 日期 (`YYYY-MM-DD`) 作为缓存时间标记。
- 若缓存中的 `date` 与当前日期不一致，会先删除旧 `proxy_cache.json`，再重建当天缓存。
- 个人代理池构建脚本就不上传到仓库了，如果没有合适的代理，可用使用本人的另一个项目（[warp-proxy-docker](https://github.com/kschen202115/warp-proxy-docker)）
- 上面那个仓库有问题，酌情使用，或者使用这个仓库的公共代理[PROXY-List](https://github.com/TheSpeedX/PROXY-List)

`proxy_cache.json`内结构如下
```bash
{
    "date": "2026-03-10",//更新时间
    "usable": [//可用列表
        {
            "proxy": "127.0.0.1:1080",//地址：端口和可用的协议
            "http": false,
            "socks4": false,
            "socks5": true
        }
    ]
}
```
## 常见问题

1. mail.tm 邮箱创建失败
- 检查网络是否可达 `https://api.mail.tm`（需要代理或直连均可）。
- 若使用代理，确认代理支持 HTTPS 请求。

2. 代理可用但注册失败率高
- 降低并发（`--workers`）。
- 清理并重新生成 `proxy_cache.json`。

3. 上传失败
- 检查 `CPA_URL` 与 `MANAGEMENT_KEY`。
- 检查上传接口路径是否与服务端一致。

