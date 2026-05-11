---
name: ip-quality-test
description: 跨平台（Windows + macOS + Linux）测当前出口 IP 的纯净度，给出 verdict（GOOD/WARN/BAD）+ ASN 类型 / VPN-Proxy-Tor / 风险分 / ChatGPT 区域解锁。基于 xykt/IPQuality 的核心维度用 Python 标准库重写，不依赖 jq/dig/bc/nc。触发条件：用户说「测一下我的 IP 质量 / 测我的 IP 纯不纯 / check ip purity / 我现在这个出口能不能跑 ChatGPT / 这个代理节点干不干净 / 帮我检测一下我的代理 IP」。
---

# ip-quality-test

跨平台 IP 纯净度体检 skill。基于 [PipeDream941/ip-quality-test](https://github.com/PipeDream941/ip-quality-test)（xykt/IPQuality 的轻量 Python 重写）。

## 何时使用

| 场景 | 用法 |
|---|---|
| 测本机出口 IP | 不传 `--proxy` |
| 测某个代理节点出口 | `--proxy http://host:port` |
| 测任意 IP 的画像 | `--ip <IP>` |

## 它能做什么

- ✅ 5 个免费数据源并发：cloudflare-trace、ipapi.is、ipinfo.io（widget/demo）、ip-api.com、ChatGPT 区域解锁
- ✅ 直接给出 verdict：`GOOD` / `WARN` / `BAD`，附原因列表
- ✅ 同时落盘 `.json` / `.ansi` / `.md` 三种报告
- ✅ 跨平台：Win 10/11、macOS、Linux 都跑同一份 `ip_quality.py`，**只要 Python 3.7+**（标准库 only）

## 它不做什么

- ❌ 不跑 400+ DNSBL 黑名单（原 bash 版用 `dig` 查，跨平台代价大；如确实需要可后续加 `dnspython`）
- ❌ 不跑流媒体全量解锁（Netflix/Disney+/Prime Video 等），只测最关键的 ChatGPT
- ❌ 不依赖任何外部 API key

## 标准用法

### 1. 本机出口 IP（最常见）

```powershell
# Windows
python C:\workspace\ip-quality-test\scripts\ip_quality.py --label local
```

```bash
# macOS / Linux
python3 ~/workspace/ip-quality-test/scripts/ip_quality.py --label local
```

或者直接用 launcher：

```powershell
& C:\workspace\ip-quality-test\run.ps1 -Label local
```

```bash
~/workspace/ip-quality-test/run.sh --label local
```

### 2. 通过代理测某节点

```powershell
python ip_quality.py --proxy http://127.0.0.1:6174 --label jp-01
```

### 3. 查任意 IP

```powershell
python ip_quality.py --ip 1.1.1.1 --label cf-dns
```

## 输出

每次跑会写到 `<repo>/reports/<label>-<timestamp>.{json,ansi,md}`：

- `.ansi` — 终端彩色（`cat` 直接看；Windows 已自动开启 VT 控制码）
- `.json` — 完整 5 源原始数据 + 聚合 summary
- `.md` — 可贴 Notion / 飞书

## verdict 规则

| verdict | 触发条件（满足任一） |
|---|---|
| `BAD` | Country ∈ {CN,RU,IR,KP,CU,SY,BY,VE} / ChatGPT 区域被屏蔽 / 任一源标 abuser / abuse_score ≥ 0.75 |
| `WARN` | 任一源标 VPN/Proxy/Tor / 任一源标 hosting/datacenter / 0.25 ≤ abuse_score < 0.75 |
| `GOOD` | 以上都不命中（住宅 ISP / 移动 / 卫星 + 低分 + ChatGPT 区域允许） |

## 决策表（README 翻译版）

| 维度 | 理想值（适合长期跑 Claude Code） |
|---|---|
| `country_code` | 非 CN/RU/IR/KP/CU/SY 等受限地区 |
| ChatGPT 解锁 | UNLOCKED（OpenAI 不拦 ≈ Anthropic 大概率也不拦）|
| `asn_type` / `company_type` | `isp` / `business` / `mobile` 优于 `hosting` |
| `is_vpn` / `is_proxy` / `is_tor` | 全 false |
| `abuse_score` | < 0.25 最佳 |

## 已知限制

1. **ipapi.is 免费匿名查询有限速**（约每分钟 60 次），批量跑节点时建议加 `sleep`
2. **chat.openai.com 返回 403** 是 Cloudflare 反爬常态，脚本以 `loc=` 区域为主判定，不以 HTTP 状态为准
3. **不带 `--proxy` 时**，测的就是 Claude Code 主进程的实际出口（如果 Claude 走系统代理）— 与"裸机出口"是否一致需自行确认

## 与其它 skill 的边界

| skill | 用途 |
|---|---|
| `ip-quality-test`（本 skill） | 测**当前**出口的纯净度（任何地方都能跑） |
| `ip-quality-check` | 通过 WebShare API **替换** 一个新的高质量住宅代理 IP |
| `ip-quality-analyzer` | 读 `ip-quality-check` 产出的报告，判断是否达标 |

## 仓库

源代码：https://github.com/PipeDream941/ip-quality-test
