"""
gan-anubis: Zero-dependency Anubis PoW solver
Supports fast / metarefresh / preact challenge modes.
"""

import sys
import re
import json
import hashlib
import time
import http.cookiejar
import urllib.request
import urllib.parse

__version__ = "1.0.0"
__all__ = ["bypass", "solve_pow"]

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
    """
    Brute-force SHA-256(randomData + nonce) until leading `difficulty` nibbles are 0.
    Returns (nonce, hash_hex).
    """
    target = "0" * difficulty
    nonce = 0
    while True:
        h = hashlib.sha256(f"{random_data}{nonce}".encode()).hexdigest()
        if h[:difficulty] == target:
            return nonce, h
        nonce += 1


def bypass(url, cookie_jar=None, verbose=True):
    """
    Bypass Anubis protection for the given URL.

    Args:
        url (str): Target URL protected by Anubis.
        cookie_jar (http.cookiejar.CookieJar, optional): Cookie jar to persist auth.
        verbose (bool): Print progress messages.

    Returns:
        str: HTML content of the page after bypassing Anubis.
    """
    if cookie_jar is None:
        cookie_jar = http.cookiejar.CookieJar()

    def log(msg):
        if verbose:
            print(msg)

    log(f"[*] Target: {url}")
    log("[*] Fetching challenge...")
    html, _ = fetch(url, cookie_jar)

    data = parse_challenge(html)
    if data is None:
        log("[+] No Anubis detected, direct access succeeded")
        return html

    algorithm    = data["rules"]["algorithm"]
    difficulty   = data["rules"]["difficulty"]
    random_data  = data["challenge"]["randomData"]
    challenge_id = data["challenge"]["id"]

    log(f"[*] Algorithm: {algorithm}, Difficulty: {difficulty}")

    parsed = urllib.parse.urlparse(url)
    base   = f"{parsed.scheme}://{parsed.netloc}"
    api    = f"{base}/.within.website/x/cmd/anubis/api/pass-challenge"

    start_time = time.time()

    if algorithm == "fast":
        log("[*] Solving PoW...")
        nonce, h = solve_pow(random_data, difficulty)
        elapsed = int((time.time() - start_time) * 1000)
        log(f"[+] Solved! nonce={nonce}, hash={h[:16]}..., elapsed={elapsed}ms")
        params = urllib.parse.urlencode({
            "id": challenge_id,
            "response": h,
            "nonce": nonce,
            "redir": url,
            "elapsedTime": elapsed,
        })

    elif algorithm == "metarefresh":
        wait = difficulty * 0.8
        log(f"[*] metarefresh, waiting {wait:.1f}s...")
        time.sleep(wait)
        elapsed = int((time.time() - start_time) * 1000)
        params = urllib.parse.urlencode({
            "id": challenge_id,
            "challenge": random_data,
            "redir": url,
        })

    elif algorithm == "preact":
        wait = difficulty * 0.08
        log(f"[*] preact, waiting {wait:.2f}s...")
        time.sleep(wait)
        result = hashlib.sha256(random_data.encode()).hexdigest()
        elapsed = int((time.time() - start_time) * 1000)
        log(f"[+] result={result[:16]}...")
        params = urllib.parse.urlencode({
            "id": challenge_id,
            "result": result,
            "redir": url,
        })

    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # Submit solution
    submit_url = f"{api}?{params}"
    log("[*] Submitting solution...")

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
            raise RuntimeError(f"Submission failed: HTTP {e.code}\n{e.read().decode()[:300]}")

    # Verify cookie
    cookies = {c.name: c.value for c in cookie_jar}
    auth_cookie = next(
        (k for k in cookies if "anubis" in k and "verification" not in k), None
    )
    if not auth_cookie:
        raise RuntimeError(f"No auth cookie received. Cookies: {list(cookies.keys())}")

    log(f"[+] Got JWT cookie! ({auth_cookie})")

    # Fetch real content
    log("[*] Fetching real content...")
    html, _ = fetch(url, cookie_jar)

    if "anubis_challenge" in html:
        raise RuntimeError("Still blocked after challenge")

    title = re.search(r"<title[^>]*>(.*?)</title>", html)
    log(f"[+] Success! title: {title.group(1) if title else '(no title)'}")

    return html
