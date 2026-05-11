# TNTCloud 节点 IP 纯净度体检

用 [xykt/IPQuality](https://github.com/xykt/IPQuality) 给 TNTCloud 各节点出口 IP 体检，挑出适合长期跑 Claude Code 的节点。

这个仓库保留脚本和使用说明，不默认提交真实测试报告，方便公开分享与二次复现。

## 前提条件

| 项 | 状态 |
|---|---|
| macOS + Homebrew | ✅ `/opt/homebrew/bin/brew` |
| 现代 bash(脚本要求 ≥ 4.0) | ✅ `brew install bash` → `/opt/homebrew/bin/bash` 5.3 |
| 依赖: `jq dig whois nmap curl bc openssl` | ✅ (`nmap` 由 brew 装) |
| TNTCloud 客户端代理 | ✅ `127.0.0.1:6174` (系统代理 + Claude `HTTPS_PROXY`) |
| Claude `HTTPS_PROXY` | `~/.claude/settings.json` → `http://127.0.0.1:6174` |

## 关键约束

1. **必须走代理跑**：不加 `-x` 测的是裸机出口（中国移动 CN），不是 Claude 实际用的 IP
2. **PATH 要把 brew bash 放前面**：脚本里有 `bash --version` 走 PATH，默认会拿到系统的 3.2 然后报错退出
3. **不要用 Docker**：macOS 上 `--net=host` 不真生效，容器看不到宿主机 `6174` 端口的代理
4. **测试期间不要切节点**：每次测试对应当前选中的那个节点，切节点要重新跑

## 目录结构

```
ip-quality-test/
├── README.md                     # 本文件
├── scripts/
│   ├── ipquality.sh              # xykt 脚本本地副本
│   └── tnt-ipcheck.sh            # 早期简版（只查 ipapi.is，已废弃）
└── reports/
    ├── .gitkeep                  # 保留目录结构
    ├── <label>-<timestamp>.ansi  # 原始 ANSI 报告（终端 cat 可看）
    ├── <label>-<timestamp>.json  # JSON 报告（用于解析/对比）
    └── <label>-<timestamp>.md    # 人类可读分析
```

## 运行命令(单节点)

```bash
git clone <your-repo-url>
cd ip-quality-test
mkdir -p reports

TS=$(date +%Y%m%d-%H%M%S)
LABEL="<节点名,如 jp-01>"

# 同时生成 ANSI(可视)+ JSON(可解析)
PATH="/opt/homebrew/bin:$PATH" /opt/homebrew/bin/bash scripts/ipquality.sh \
  -x http://127.0.0.1:6174 -n -o reports/${LABEL}-${TS}.ansi

PATH="/opt/homebrew/bin:$PATH" /opt/homebrew/bin/bash scripts/ipquality.sh \
  -x http://127.0.0.1:6174 -n -j -o reports/${LABEL}-${TS}.json
```

每次约 30-90 秒（9 家风险库 + 400+ DNSBL + 流媒体解锁测试）。

## 结果解读维度(按对 Claude 的重要性)

| 维度 | 字段 | Claude 安全的理想值 |
|---|---|---|
| **地区** | `Factor.CountryCode` | 不在 CN/RU/IR/KP/CU/SY 等受限地区 |
| **ChatGPT 解锁** | `Media.ChatGPT.Status` | `解锁` - OpenAI 不拦 ≈ Anthropic 大概率也不拦 |
| **类型（机房？）** | `Type.Usage` | 多家不标“机房”为佳；住宅/移动/原生最干净 |
| **Proxy / VPN 标识** | `Factor.Proxy` `Factor.VPN` | 多家 false |
| **风险分** | `Score.IP2LOCATION` `Score.SCAMALYTICS` `Score.AbuseIPDB` `Score.IPQS` | 都低于 25；IP2LOC 越低越好 |
| **DNSBL 命中** | `Mail.DNSBlacklist.Blacklisted` | 0 最佳;1-3 可接受;>5 谨慎 |
| **Abuser** | `Factor.Abuser` | 多家 false |

简单决策表:

- 任何家给 `Country=CN`（或受限）→ 淘汰
- ChatGPT 不解锁 → 高风险,淘汰
- IP2LOC 风险 ≥ 75 + 多家标 VPN/Proxy → 不建议长期用
- 全部 false / 低分 + ChatGPT 解锁 → 优选

## 工作流(批量)

```
[切到节点 A] → 跑命令(LABEL=A) → [切到节点 B] → 跑命令(LABEL=B) → ...
                ↓
        最后用汇总脚本对所有 reports/*.json 做横向对比
```

## 隐私说明

- `reports/` 下的真实检测结果默认不纳入版本控制
- 如果你需要分享样例，建议手动脱敏后再单独提交

## 后续计划

汇总脚本待写，完成所有节点测试后再做。
