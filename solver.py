#!/usr/bin/env python3
"""
anubis_solver.py - Anubis PoW / metarefresh / preact bypass
用法:
  python3 anubis_solver.py <url>
  python3 anubis_solver.py <url> --cookie-file cookies.txt
  python3 anubis_solver.py <url> --output page.html
  python3 anubis_solver.py <url> --no-save
"""

import sys
import re
import json
import hashlib
import time
import argparse
import http.cookiejar
import urllib.request
import urllib.parse

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"

def encode_url(url):
    parsed = urllib.parse.urlparse(url)
    encoded_path = urllib.parse.quote(parsed.path, safe="/:@!$&'()*+,;=")
    encoded_query = urllib.parse.quote(parsed.query, safe="=&+:@!$'()*,;/?")
    return parsed._replace(path=encoded_path, query=encoded_query).geturl()

def fetch(url, cookie_jar):
    url = encode_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    with opener.open(req) as res:
        return res.read().decode("utf-8", errors="replace"), res.geturl()

def parse_challenge(html):
    start = html.find("anubis_challenge")
    if start == -1:
        return None
    end = html.find("</script>", start)
    raw = html[start:end]
    raw = raw[raw.find("{"):]
    return json.loads(raw)

def solve_pow(random_data, difficulty):
    """fast: 暴力算 SHA-256(randomData + nonce) 直到前 difficulty 個 nibble 是 0"""
    target = "0" * difficulty
    nonce = 0
    while True:
        h = hashlib.sha256(f"{random_data}{nonce}".encode()).hexdigest()
        if h[:difficulty] == target:
            return nonce, h
        nonce += 1

def bypass(url, cookie_jar):
    print(f"[*] 目標: {url}")
    print("[*] 取得 challenge...")
    html, _ = fetch(url, cookie_jar)

    data = parse_challenge(html)
    if data is None:
        print("[+] 沒有偵測到 Anubis，直接存取成功")
        return html

    algorithm    = data["rules"]["algorithm"]
    difficulty   = data["rules"]["difficulty"]
    random_data  = data["challenge"]["randomData"]
    challenge_id = data["challenge"]["id"]

    print(f"[*] 演算法: {algorithm}, 難度: {difficulty}")
    print(f"[*] challenge id: {challenge_id}")

    parsed = urllib.parse.urlparse(url)
    base   = f"{parsed.scheme}://{parsed.netloc}"
    api    = f"{base}/.within.website/x/cmd/anubis/api/pass-challenge"

    start_time = time.time()

    if algorithm == "fast":
        # 算 SHA-256(randomData + nonce) 找前 difficulty 個 nibble 為 0
        print("[*] 計算 PoW...")
        nonce, h = solve_pow(random_data, difficulty)
        elapsed = int((time.time() - start_time) * 1000)
        print(f"[+] 解出！nonce={nonce}, hash={h[:16]}..., 耗時={elapsed}ms")
        params = urllib.parse.urlencode({
            "id": challenge_id,
            "response": h,
            "nonce": nonce,
            "redir": url,
            "elapsedTime": elapsed,
        })

    elif algorithm == "metarefresh":
        # 等 difficulty * 0.8 秒，送回 randomData 本身
        wait = difficulty * 0.8
        print(f"[*] metarefresh，等待 {wait:.1f} 秒...")
        time.sleep(wait)
        elapsed = int((time.time() - start_time) * 1000)
        params = urllib.parse.urlencode({
            "id": challenge_id,
            "challenge": random_data,
            "redir": url,
        })

    elif algorithm == "preact":
        # 等 difficulty * 0.08 秒，送回 SHA-256(randomData)
        wait = difficulty * 0.08
        print(f"[*] preact，等待 {wait:.2f} 秒...")
        time.sleep(wait)
        result = hashlib.sha256(random_data.encode()).hexdigest()
        elapsed = int((time.time() - start_time) * 1000)
        print(f"[+] result={result[:16]}...")
        params = urllib.parse.urlencode({
            "id": challenge_id,
            "result": result,
            "redir": url,
        })

    else:
        print(f"[-] 未知演算法: {algorithm}，請回報此問題")
        sys.exit(1)

    # 送答案
    submit_url = f"{api}?{params}"
    print("[*] 提交答案...")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        NoRedirect(),
    )
    req = urllib.request.Request(submit_url, headers={"User-Agent": UA})
    try:
        opener.open(req)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            print(f"[-] 提交失敗: HTTP {e.code}")
            print(e.read().decode()[:300])
            sys.exit(1)

    cookies = {c.name: c.value for c in cookie_jar}
    # 動態偵測：找任何包含 "anubis" 且不含 "verification" 的 cookie
    auth_cookie = next(
        (k for k in cookies if "anubis" in k and "verification" not in k), None
    )
    if auth_cookie:
        print(f"[+] 成功拿到 JWT cookie！({auth_cookie})")
    else:
        print("[-] 沒有拿到 cookie")
        print(f"    現有 cookies: {list(cookies.keys())}")
        sys.exit(1)

    # 帶 cookie 存取真實內容
    print("[*] 存取真實內容...")
    html, _ = fetch(url, cookie_jar)

    if "anubis_challenge" in html:
        print("[-] 還是被擋住了")
    else:
        title = re.search(r"<title[^>]*>(.*?)</title>", html)
        print(f"[+] 成功！title: {title.group(1) if title else '(無 title)'}")

    return html


def url_to_filename(url):
    parsed = urllib.parse.urlparse(url)
    path  = parsed.path.strip("/").replace("/", "_")
    query = urllib.parse.unquote(parsed.query).replace("=", "-").replace("&", "_")
    name  = parsed.netloc
    if path:
        name += "_" + path
    if query:
        name += "_" + query
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name[:100] + ".html"


def main():
    parser = argparse.ArgumentParser(description="Anubis PoW solver (fast / metarefresh / preact)")
    parser.add_argument("url", help="目標 URL")
    parser.add_argument("--cookie-file", default=None, help="cookie 儲存路徑")
    parser.add_argument("--output", default=None, help="儲存頁面 HTML（預設自動從 URL 產生檔名）")
    parser.add_argument("--no-save", action="store_true", help="不儲存 HTML")
    args = parser.parse_args()

    cookie_jar = http.cookiejar.MozillaCookieJar()
    if args.cookie_file:
        try:
            cookie_jar.load(args.cookie_file, ignore_discard=True)
            print(f"[*] 載入既有 cookie: {args.cookie_file}")
        except FileNotFoundError:
            pass

    html = bypass(args.url, cookie_jar)

    if args.cookie_file:
        cookie_jar.save(args.cookie_file, ignore_discard=True)
        print(f"[*] cookie 已儲存至 {args.cookie_file}")

    if not args.no_save:
        output = args.output or url_to_filename(args.url)
        with open(output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[*] 頁面已儲存至 {output}")


if __name__ == "__main__":
    main()
