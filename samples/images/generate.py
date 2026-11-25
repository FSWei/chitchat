#!/usr/bin/env python3
"""生成示例图。

两种后端：

  3.0（默认，火山视觉智能，用 AK/SK）
    VOLCENGINE_AK / VOLCENGINE_SK
    python generate.py --provider volcengine3

  5.0 Flash（火山方舟，用 ARK_API_KEY）
    ARK_API_KEY
    python generate.py --provider ark

图片存到当前目录；URL 24 小时过期，脚本会立刻下载。
提示词全部来自 prompts.json，改图先改那个文件，别在代码里改。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTS = HERE / "prompts.json"
WIDTH, HEIGHT = 1024, 1360  # 3.0 竖版自拍；宽高乘积 < 2048×2048


def _download(url: str, stem: Path) -> Path:
    """下载并按真实字节定扩展名——接口常返回 JPEG，别再叫 .png。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if data[:2] == b"\xff\xd8":
        ext = ".jpg"
    elif data[:4] == b"\x89PNG":
        ext = ".png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    else:
        ext = ".bin"
    out = stem.with_suffix(ext)
    out.write_bytes(data)
    return out


def gen_volcengine3(prompt: str, stem: Path) -> Path:
    from volcengine.visual.VisualService import VisualService

    service = VisualService()
    service.set_ak(os.environ["VOLCENGINE_AK"])
    service.set_sk(os.environ["VOLCENGINE_SK"])
    resp = service.cv_process(
        {
            "req_key": "high_aes_general_v30l_zt2i",
            "prompt": prompt,
            "width": WIDTH,
            "height": HEIGHT,
            "return_url": True,
            "logo_info": {"add_logo": False},
        }
    )
    if resp.get("code") != 10000:
        raise RuntimeError(f"3.0 失败: {resp.get('code')} {resp.get('message')}")
    return _download(resp["data"]["image_urls"][0], stem)


def gen_ark(prompt: str, stem: Path) -> Path:
    import requests

    r = requests.post(
        "https://ark.cn-beijing.volces.com/api/v3/images/generations",
        headers={"Authorization": f"Bearer {os.environ['ARK_API_KEY']}"},
        json={
            "model": "doubao-seedream-5-0-flash-260915",
            "prompt": prompt,
            "size": "2K",
            "output_format": "png",
            "response_format": "url",
            "watermark": False,
        },
        timeout=180,
    )
    r.raise_for_status()
    return _download(r.json()["data"][0]["url"], stem)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["volcengine3", "ark"], default="volcengine3")
    ap.add_argument("--only", default="", help="只生成名字里包含这个子串的那几张")
    ap.add_argument("--out", default=str(HERE))
    args = ap.parse_args(argv)

    gen = gen_volcengine3 if args.provider == "volcengine3" else gen_ark
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    items = json.loads(PROMPTS.read_text(encoding="utf-8"))
    if args.only:
        items = [i for i in items if args.only in i["name"]]

    ok = fail = 0
    for item in items:
        stem = out_dir / item["name"]
        if any(stem.with_suffix(e).exists() for e in (".jpg", ".png", ".webp")):
            print(f"· 跳过 {item['name']}（已存在）")
            continue
        try:
            saved = gen(item["prompt"], stem)
            ok += 1
            print(f"✓ {saved.name}")
        except Exception as exc:  # 单张失败不能中断整批
            fail += 1
            print(f"✗ {item['name']}: {type(exc).__name__} {str(exc)[:120]}")
        time.sleep(2)
    print(f"done: ok={ok} fail={fail} → {out_dir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
