#!/usr/bin/env python3
"""
Download @cosme ranking product data and main product images.

Examples:
python3 cosme_ranking_scraper.py --item-id 916
python3 cosme_ranking_scraper.py --item-ids 916 1008 1013 918 964
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL_TEMPLATE = "https://www.cosme.net/categories/item/{item_id}/ranking/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)

# Common base-makeup item IDs confirmed from @cosme category pages on 2026-06-16.
CATEGORY_PRESETS: dict[str, dict[str, str]] = {
    "916": {"slug": "foundation", "label": "ファンデーション"},
    "917": {"slug": "primer_concealer", "label": "化粧下地・コンシーラー"},
    "918": {"slug": "face_powder", "label": "フェイスパウダー"},
    "964": {"slug": "fix_mist", "label": "フィックスミスト"},
    "1008": {"slug": "makeup_base", "label": "化粧下地"},
    "1013": {"slug": "concealer", "label": "コンシーラー"},
}
BASE_MAKEUP_ITEM_IDS = ["916", "1008", "1013", "918", "964"]
DEFAULT_DATE_STAMP = datetime.now().strftime("%Y%m%d")


@dataclass
class ProductRow:
    rank: int | None
    product_id: str
    brand: str
    product_name: str
    categories: str
    rating: str
    review_count: int | None
    attention_count: int | None
    capacity_price: str
    release_date: str
    product_url: str
    shopping_url: str
    image_url: str
    image_file: str


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return text or "category"


def category_slug(item_id: str) -> str:
    preset = CATEGORY_PRESETS.get(item_id)
    return preset["slug"] if preset else f"item_{item_id}"


def category_label(item_id: str) -> str:
    preset = CATEGORY_PRESETS.get(item_id)
    return preset["label"] if preset else f"item/{item_id}"


def default_basename(item_id: str) -> str:
    return f"cosme_{category_slug(item_id)}_ranking"


def default_output_dir(item_id: str) -> Path:
    return Path("data") / f"{default_basename(item_id)}_{DEFAULT_DATE_STAMP}"


def to_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def decode_response(resp: requests.Response) -> str:
    if not resp.encoding or resp.encoding.lower() in {"iso-8859-1", "ascii"}:
        resp.encoding = "cp932"
    return resp.text


def fetch(session: requests.Session, url: str, timeout: int = 30) -> str:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return decode_response(resp)


def ranking_page_url(base_url: str, page: int) -> str:
    if page <= 1:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}page={page}"


def parse_product_id(url: str) -> str:
    match = re.search(r"/products/(\d+)/", url)
    return match.group(1) if match else ""


def absolute_url(base_url: str, maybe_url: str | None) -> str:
    if not maybe_url:
        return ""
    return urljoin(base_url, maybe_url)


def parse_rank(item: BeautifulSoup, fallback: int) -> int | None:
    rank_node = item.select_one(".rank-num")
    if not rank_node:
        return fallback
    text = clean_text(rank_node.get_text(" ", strip=True))
    rank = to_int(text)
    if rank:
        return rank
    img = rank_node.find("img", alt=True)
    return to_int(img["alt"]) if img else fallback


def parse_list_item(item: BeautifulSoup, base_url: str, fallback_rank: int) -> dict:
    product_link = item.select_one("h4.item a[href*='/products/']")
    if not product_link:
        product_link = item.select_one("dd.pic a[href*='/products/']")
    product_url = absolute_url(base_url, product_link.get("href") if product_link else "")

    image = item.select_one("dd.pic img")
    image_url = absolute_url(base_url, image.get("src") if image else "")

    brand = clean_text(item.select_one(".brand a").get_text(" ", strip=True) if item.select_one(".brand a") else "")
    product_name = clean_text(product_link.get_text(" ", strip=True) if product_link else "")
    categories = " / ".join(clean_text(a.get_text(" ", strip=True)) for a in item.select(".category a"))

    rating_node = item.select_one(".reviewer-average")
    rating = clean_text(rating_node.get_text(" ", strip=True) if rating_node else "")

    review_node = item.select_one(".votes .count span, .votes .count")
    review_count = to_int(review_node.get_text(" ", strip=True) if review_node else "")

    price_text = clean_text(item.select_one(".price").get_text(" ", strip=True) if item.select_one(".price") else "")
    capacity_price = re.sub(r"^税込価格：", "", price_text).strip()

    release_text = clean_text(item.select_one(".onsale").get_text(" ", strip=True) if item.select_one(".onsale") else "")
    release_date = re.sub(r"^発売日：", "", release_text).strip()

    shop = item.select_one(".btn-cmn-buy[href]")
    shopping_url = absolute_url(base_url, shop.get("href") if shop else "")

    return {
        "rank": parse_rank(item, fallback_rank),
        "product_id": parse_product_id(product_url),
        "brand": brand,
        "product_name": product_name,
        "categories": categories,
        "rating": rating,
        "review_count": review_count,
        "capacity_price": capacity_price,
        "release_date": release_date,
        "product_url": product_url,
        "shopping_url": shopping_url,
        "image_url": image_url,
    }


def parse_detail_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    detail: dict[str, str | int | None] = {}

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        match = re.search(r"注目人数([\d,]+)人", og_title["content"])
        detail["attention_count"] = to_int(match.group(1)) if match else None

    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        detail["image_url"] = og_image["content"]

    for li in soup.select("ul.info-rating li"):
        label = clean_text(li.select_one(".info-ttl").get_text(" ", strip=True) if li.select_one(".info-ttl") else "")
        value = clean_text(li.select_one(".info-desc").get_text(" ", strip=True) if li.select_one(".info-desc") else "")
        if label == "容量・税込価格" and value:
            detail["capacity_price"] = value
        elif label == "発売日" and value:
            detail["release_date"] = value
        elif label == "クチコミ評価" and value:
            rating_match = re.search(r"\d+(?:\.\d+)?", value)
            if rating_match:
                detail["rating"] = rating_match.group(0)

    review_count_node = soup.select_one("ul.rev-cnt span.count")
    if review_count_node:
        detail["review_count"] = to_int(review_count_node.get_text(" ", strip=True))

    return detail


def image_extension(url: str, content_type: str | None) -> str:
    parsed_ext = Path(urlparse(url).path).suffix.lower()
    if parsed_ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return parsed_ext
    guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
    return guessed or ".jpg"


def download_image(session: requests.Session, url: str, output_dir: Path, rank: int | None, product_id: str) -> str:
    if not url:
        return ""
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    ext = image_extension(url, resp.headers.get("content-type"))
    safe_rank = f"{rank:03d}" if rank else "000"
    filename = f"{safe_rank}_{product_id or 'product'}{ext}"
    path = output_dir / filename
    path.write_bytes(resp.content)
    return str(path)


def collect_products(
    base_url: str,
    pages: int,
    output_dir: Path,
    delay: float,
    download_images: bool,
) -> list[ProductRow]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"})

    rows: list[ProductRow] = []
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    for page in range(1, pages + 1):
        page_url = ranking_page_url(base_url, page)
        html = fetch(session, page_url)
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("div.keyword-ranking-item")
        if not items:
            raise RuntimeError(f"No ranking items found on {page_url}")

        for index, item in enumerate(items, start=1):
            fallback_rank = (page - 1) * 10 + index
            data = parse_list_item(item, page_url, fallback_rank)

            if data["product_url"]:
                time.sleep(delay)
                try:
                    detail = parse_detail_page(fetch(session, data["product_url"]))
                    data.update({k: v for k, v in detail.items() if v not in ("", None)})
                except requests.RequestException as exc:
                    print(f"[warn] detail fetch failed: {data['product_url']} ({exc})", flush=True)
                except Exception as exc:
                    print(f"[warn] detail parse failed: {data['product_url']} ({exc})", flush=True)

            local_image = ""
            if download_images and data.get("image_url"):
                time.sleep(delay)
                try:
                    local_image = download_image(
                        session,
                        data["image_url"],
                        image_dir,
                        data.get("rank"),
                        data.get("product_id", ""),
                    )
                except requests.RequestException as exc:
                    print(f"[warn] image download failed: {data['image_url']} ({exc})", flush=True)

            rows.append(
                ProductRow(
                    rank=data.get("rank"),
                    product_id=data.get("product_id", ""),
                    brand=data.get("brand", ""),
                    product_name=data.get("product_name", ""),
                    categories=data.get("categories", ""),
                    rating=data.get("rating", ""),
                    review_count=data.get("review_count"),
                    attention_count=data.get("attention_count"),
                    capacity_price=data.get("capacity_price", ""),
                    release_date=data.get("release_date", ""),
                    product_url=data.get("product_url", ""),
                    shopping_url=data.get("shopping_url", ""),
                    image_url=data.get("image_url", ""),
                    image_file=local_image,
                )
            )

        time.sleep(delay)

    return rows


def save_outputs(rows: Iterable[ProductRow], output_dir: Path, basename: str) -> None:
    data = [asdict(row) for row in rows]
    csv_path = output_dir / f"{basename}.csv"
    json_path = output_dir / f"{basename}.json"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(data)} products", flush=True)
    print(f"CSV : {csv_path}", flush=True)
    print(f"JSON: {json_path}", flush=True)
    print(f"Images: {output_dir / 'images'}", flush=True)


def resolve_item_ids(args: argparse.Namespace) -> list[str]:
    if args.base_makeup:
        return BASE_MAKEUP_ITEM_IDS
    if args.item_ids:
        return [str(item_id) for item_id in args.item_ids]
    return [str(args.item_id)]


def scrape_one_category(item_id: str, pages: int, delay: float, no_images: bool) -> None:
    base_url = BASE_URL_TEMPLATE.format(item_id=item_id)
    output_dir = default_output_dir(item_id)
    basename = default_basename(item_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"==> item/{item_id} {category_label(item_id)}", flush=True)
    print(f"URL : {base_url}", flush=True)
    print(f"OUT : {output_dir}", flush=True)

    rows = collect_products(base_url, pages, output_dir, delay, not no_images)
    save_outputs(rows, output_dir, basename)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape @cosme ranking product info and images by item ID.")
    parser.add_argument("--item-id", default="916", help="Single @cosme item ID, for example 916.")
    parser.add_argument("--item-ids", nargs="+", help="Multiple @cosme item IDs.")
    parser.add_argument("--base-makeup", action="store_true", help="Scrape 916, 1008, 1013, 918, 964 together.")
    parser.add_argument("--pages", type=int, default=5, help="Number of ranking pages to scrape. 5 pages = 1-50.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds.")
    parser.add_argument("--no-images", action="store_true", help="Skip image downloads.")
    args = parser.parse_args()

    for item_id in resolve_item_ids(args):
        scrape_one_category(item_id, args.pages, args.delay, args.no_images)


if __name__ == "__main__":
    main()
