"""
CLI entry point: python -m gan_anubis <url>
"""

import sys
import re
import argparse
import http.cookiejar
import urllib.parse

from . import bypass, __version__


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
    parser = argparse.ArgumentParser(
        prog="gan-anubis",
        description=f"Anubis PoW solver v{__version__} (fast / metarefresh / preact)",
    )
    parser.add_argument("url", help="Target URL")
    parser.add_argument("--cookie-file", default=None, help="Cookie file path (reuse across runs)")
    parser.add_argument("--output", default=None, help="Output HTML filename (auto-generated if omitted)")
    parser.add_argument("--no-save", action="store_true", help="Don't save HTML")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args()

    cookie_jar = http.cookiejar.MozillaCookieJar()
    if args.cookie_file:
        try:
            cookie_jar.load(args.cookie_file, ignore_discard=True)
            if not args.quiet:
                print(f"[*] Loaded cookies: {args.cookie_file}")
        except FileNotFoundError:
            pass

    try:
        html = bypass(args.url, cookie_jar=cookie_jar, verbose=not args.quiet)
    except Exception as e:
        print(f"[-] Failed: {e}", file=sys.stderr)
        sys.exit(1)

    if args.cookie_file:
        cookie_jar.save(args.cookie_file, ignore_discard=True)
        if not args.quiet:
            print(f"[*] Cookies saved: {args.cookie_file}")

    if not args.no_save:
        output = args.output or url_to_filename(args.url)
        with open(output, "w", encoding="utf-8") as f:
            f.write(html)
        if not args.quiet:
            print(f"[*] Saved: {output}")


if __name__ == "__main__":
    main()
