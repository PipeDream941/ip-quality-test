# ip-quality-test

给出口 IP 做纯净度体检，挑出适合长期跑 Claude Code 的节点 / 网络。

仓库提供两套实现：

| 实现 | 平台 | 依赖 | 测什么 | 推荐场景 |
|---|---|---|---|---|
| **轻量版** `scripts/ip_quality.py` | Win + macOS + Linux | 仅 Python 3.7+（标准库） | 5 个聚合源 + ChatGPT 区域解锁 | **日常 / Claude Code skill 调用** |
| 重型版 `scripts/ipquality.sh` | 主要 macOS | bash 4+ / `jq dig nc bc curl` | 9 家风险库 + 400+ DNSBL + 流媒体全量解锁 | 需要 DNSBL / 流媒体全量数据时 |

> 仓库保留脚本和使用说明，不默认提交真实测试报告，方便公开分享与二次复现。

---

## 一、轻量版（推荐 · 跨平台 Python）

### 前提条件

- Python 3.7+（macOS 自带 / `brew install python` / `winget install Python.Python.3.12` / `apt install python3`）
- 不需要 jq / dig / bc / nc / nmap / openssl
- 不需要任何 API key

### 运行命令

**Windows（PowerShell）**

```powershell
git clone https://github.com/PipeDream941/ip-quality-test.git
cd ip-quality-test
.\run.ps1 -Label local
```

**macOS / Linux**

```bash
git clone https://github.com/PipeDream941/ip-quality-test.git
cd ip-quality-test
./run.sh --label local
```

**直接调 Python（跨平台同写法）**

```bash
python scripts/ip_quality.py --label local
python scripts/ip_quality.py --proxy http://127.0.0.1:6174 --label jp-01   # 通过代理测
python scripts/ip_quality.py --ip 1.1.1.1 --label cf-dns                   # 测任意 IP
```

每次约 3–10 秒（5 源并发）。

### 输出示例

```
================================================================
 IP Quality Report   verdict:  GOOD
================================================================
  IP        : 129.126.148.246
  Location  : Singapore (SG)  - Novena
  ASN       : AS17547  M1 NET LTD
  Type      : asn=isp  company=isp
  Abuse sc. : 0.001
  Flags     : vpn=no  proxy=no  tor=no  relay=no  hosting_or_dc=no  abuser=no  mobile=no
  ChatGPT   : UNLOCKED  (loc=SG)
```

报告同时落盘到 `reports/<label>-<timestamp>.{json,ansi,md}`。

### Verdict 规则

| verdict | 触发条件（满足任一即触发） |
|---|---|
| `BAD` | `country_code ∈ {CN,RU,IR,KP,CU,SY,BY,VE}` / ChatGPT 区域被屏蔽 / 任一源标 abuser / abuse_score ≥ 0.75 |
| `WARN` | 任一源标 VPN/Proxy/Tor / 标 hosting/datacenter / 0.25 ≤ abuse_score < 0.75 |
| `GOOD` | 全部未命中 + 区域允许 ChatGPT |

### 数据源

| 来源 | 字段 | 是否需要 key |
|---|---|---|
| `cloudflare-trace` | `ip`, `loc` | 否 |
| `api.ipapi.is` | ASN/Country/Company.Type/is_vpn/is_proxy/is_tor/abuser_score | 否（限速 ~60/min） |
| `ipinfo.io/widget/demo` | Country/ASN/privacy.{vpn,proxy,tor,hosting,relay} | 否 |
| `ip-api.com` | Country/ASN/proxy/hosting/mobile | 否 |
| `chatgpt`（chat.openai.com + chatgpt.com） | 区域解锁（以 trace 的 `loc=` 为主判定） | 否 |

### 已知限制

1. 不跑 400+ DNSBL（需重型版的 `dig`）
2. 不跑流媒体全量（Netflix/Disney+/Prime Video 等）
3. `chat.openai.com` 对未带 cookie 的请求返回 403 是常态，脚本以 `loc=` 区域为主判定

---

## 二、重型版（mac + Claude 出口代理）

基于 [xykt/IPQuality](https://github.com/xykt/IPQuality)。

### 前提条件

| 项 | 状态 |
|---|---|
| macOS + Homebrew | ✅ `/opt/homebrew/bin/brew` |
| 现代 bash(脚本要求 ≥ 4.0) | ✅ `brew install bash` → `/opt/homebrew/bin/bash` 5.3 |
| 依赖: `jq dig whois nmap curl bc openssl` | ✅ (`nmap` 由 brew 装) |
| TNTCloud 客户端代理 | ✅ `127.0.0.1:6174` (系统代理 + Claude `HTTPS_PROXY`) |

### 关键约束

1. **必须走代理跑**：不加 `-x` 测的是裸机出口（中国移动 CN），不是 Claude 实际用的 IP
2. **PATH 要把 brew bash 放前面**：脚本里有 `bash --version` 走 PATH，默认会拿到系统的 3.2 然后报错退出
3. **不要用 Docker**：macOS 上 `--net=host` 不真生效，容器看不到宿主机 `6174` 端口的代理
4. **测试期间不要切节点**：每次测试对应当前选中的那个节点，切节点要重新跑

### 运行命令

```bash
TS=$(date +%Y%m%d-%H%M%S)
LABEL="jp-01"

PATH="/opt/homebrew/bin:$PATH" /opt/homebrew/bin/bash scripts/ipquality.sh \
  -x http://127.0.0.1:6174 -n -o reports/${LABEL}-${TS}.ansi

PATH="/opt/homebrew/bin:$PATH" /opt/homebrew/bin/bash scripts/ipquality.sh \
  -x http://127.0.0.1:6174 -n -j -o reports/${LABEL}-${TS}.json
```

每次约 30–90 秒。

---

## 目录结构

```
ip-quality-test/
├── README.md
├── SKILL.md                  # Claude Code skill 入口（轻量版）
├── run.ps1                   # Windows launcher
├── run.sh                    # macOS/Linux launcher
├── scripts/
│   ├── ip_quality.py         # 轻量版核心（Python 标准库）
│   ├── ipquality.sh          # 重型版（xykt 脚本本地副本）
│   └── tnt-ipcheck.sh        # 早期简版（已废弃）
└── reports/
    ├── .gitkeep
    ├── <label>-<timestamp>.ansi
    ├── <label>-<timestamp>.json
    └── <label>-<timestamp>.md
```

## 解读维度（按对 Claude 的重要性）

| 维度 | 轻量版字段 | 理想值 |
|---|---|---|
| **地区** | `summary.country_code` | 非 CN/RU/IR/KP/CU/SY/BY/VE |
| **ChatGPT 解锁** | `summary.chatgpt_unlocked` | `true`（OpenAI 不拦 ≈ Anthropic 大概率也不拦）|
| **类型（机房？）** | `summary.asn_type` / `summary.company_type` | `isp` / `business` / `mobile` 优于 `hosting` |
| **Proxy/VPN/Tor** | `summary.flags.{vpn,proxy,tor,relay}` | 全 false |
| **风险分** | `summary.abuse_score`（ipapi.is）| < 0.25 |
| **DNSBL 命中** | —（仅重型版） | 0 最佳；1–3 可接受；>5 谨慎 |
| **Abuser** | `summary.flags.abuser` | false |

## 工作流（批量节点）

```
[切到节点 A] → 跑命令(LABEL=A) → [切到节点 B] → 跑命令(LABEL=B) → ...
                ↓
        最后对所有 reports/*.json 做横向对比
```

## 隐私说明

- `reports/` 下的真实检测结果默认不纳入版本控制
- 如果你需要分享样例，建议手动脱敏后再单独提交

## 作为 Claude Code skill 使用

把仓库挂到 `~/.claude/skills/ip-quality-test`（Windows 用 `mklink /J`，mac/Linux 用 `ln -s`）后，Claude 会自动识别 `SKILL.md`，遇到「测我的 IP 质量 / check IP purity / ChatGPT 解锁吗」等表述时自动调用。

详见 `SKILL.md`。

## 后续计划

- [ ] 加 `dnspython` 可选支持，补 DNSBL 维度
- [ ] 加 Netflix / Disney+ / Prime Video / YouTube Premium 流媒体解锁检测
- [ ] 批量汇总脚本（`reports/*.json` → 横向对比表）
