# gan-anubis 淦 Anubis

> A minimal, zero-dependency Python PoC that bypasses all three Anubis challenge modes.  
> 零依賴 Python 概念驗證，繞過 Anubis 全部三種挑戰模式。

---

## What is Anubis? / Anubis 是什麼？

[Anubis](https://github.com/TecharoHQ/anubis) is a proof-of-work reverse proxy designed to block AI scrapers. It claims to force bots to run a full Chrome browser (~500MB RAM) just to solve its challenges.

[Anubis](https://github.com/TecharoHQ/anubis) 是一個工作量證明反向代理，設計用來阻擋 AI 爬蟲。官方宣稱爬蟲必須跑完整的 Chrome 瀏覽器（~500MB RAM）才能解題。

**This PoC proves otherwise. / 本專案證明並非如此。**

---

## Results / 結果

| | Headless Chrome | **gan-anubis** |
|---|---|---|
| RAM | ~500MB | ~20MB |
| Solve time (difficulty=2) | ~1.35s | **<10ms** |
| Dependencies | Chrome + Playwright | **None (stdlib only)** |
| Lines of code | — | ~150 |

---

## Supported Modes / 支援模式

| Mode | Logic |
|------|-------|
| `fast` | Brute-force `SHA-256(randomData + nonce)` until leading `difficulty` nibbles are `0` |
| `metarefresh` | Wait `difficulty × 0.8s`, return `randomData` as-is |
| `preact` | Wait `difficulty × 0.08s`, return `SHA-256(randomData)` |

Cookie valid for **7 days** — solve once, scrape freely.  
Cookie 有效期 **7 天**，解一次就能爬一週。

---

## Why existing Python solvers are wrong / 為什麼現有 Python solver 是錯的

The only other Python solver on PyPI ([anubis-solver](https://pypi.org/project/anubis-solver/)) has two critical bugs:

PyPI 上唯一的 Python solver 有兩個關鍵 bug：

**Bug 1: Wrong nibble check / nibble 檢查錯誤**

```python
# ❌ Wrong: checks leading bytes (256x harder than needed)
if all(b == 0 for b in h[:difficulty]):

# ✅ Correct: checks leading nibbles (hex characters)
if h[:difficulty] == '0' * difficulty:
```

**Bug 2: Missing `id` parameter / 缺少 `id` 參數**

```python
# ❌ Wrong: always returns HTTP 500
"pass-challenge?response={hash}&nonce={nonce}&redir=/"

# ✅ Correct
"pass-challenge?id={id}&response={hash}&nonce={nonce}&redir=/"
```

This PoC was reverse-engineered directly from Anubis source code (`main.mjs`, `pow_native.go`, `preact.go`).  
本專案直接從 Anubis 原始碼逆向工程而來。

---

## Usage / 使用方式

No installation required. Python 3.6+ only.  
不需要安裝任何套件，Python 3.6+ 即可。

```bash
# Basic / 基本用法
python3 solver.py "https://example.com/"

# Save cookie for reuse (valid 7 days) / 儲存 cookie 重複使用（有效 7 天）
python3 solver.py "https://example.com/" --cookie-file cookies.txt

# Custom output filename / 自訂輸出檔名
python3 solver.py "https://example.com/" --output result.html

# Don't save HTML / 不儲存 HTML
python3 solver.py "https://example.com/" --no-save
```

### Example output / 範例輸出

```
[*] 目標: https://example.com/
[*] 取得 challenge...
[*] 演算法: fast, 難度: 2
[*] challenge id: 019ea667-c8f8-...
[*] 計算 PoW...
[+] 解出！nonce=171, hash=00a3225f..., 耗時=3ms
[*] 提交答案...
[+] 成功拿到 JWT cookie！
[*] 存取真實內容...
[+] 成功！title: Example Site
```

---

## How it works / 原理

```
1. GET target URL (with cookie jar)
   → Server returns challenge page with JSON embedded in <script> tag

2. Parse challenge JSON:
   { "rules": { "algorithm": "fast", "difficulty": 2 },
     "challenge": { "id": "...", "randomData": "..." } }

3. Solve based on algorithm:
   fast        → SHA-256(randomData + nonce) with N leading zero nibbles
   metarefresh → return randomData after waiting difficulty × 0.8s
   preact      → return SHA-256(randomData) after waiting difficulty × 0.08s

4. POST solution to /.within.website/x/cmd/anubis/api/pass-challenge
   → Server verifies, issues EdDSA-signed JWT cookie (valid 7 days)

5. Use cookie for subsequent requests — no re-solving needed
```

---

## Tested on / 測試環境

- Anubis `v1.25.1` (latest as of June 2026)
- Tested on Android (Termux) and Linux x86_64
- All three challenge modes verified

---

## Security note / 安全說明

This is a **proof of concept** for educational and research purposes.  
The goal is to demonstrate that PoW-based bot protection has fundamental limitations against determined scrapers.

本專案僅供**教育與研究目的**的概念驗證。  
目的是說明基於工作量證明的機器人防護對有心的爬蟲存在根本性的局限。

> As Tavis Ormandy noted: *"I don't think we reach a single cent per month in compute costs until several million sites have deployed Anubis."*

---

## License / 授權

MIT
