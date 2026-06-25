#!/usr/bin/env python3
"""Use Chanmama trending data to generate an MVP shortlist.

This script implements the first-stage product selection MVP:
1. Fetch trending products from Chanmama
2. Filter by category and price band
3. Score candidates by growth, search demand, competition, and channel spread
4. Penalize products that appear overly dependent on a tiny number of creators
5. Output top-N products as JSON and a readable terminal table

Notes:
- This is an initial shortlist tool. Real margin validation still requires 1688
  supplier matching, which is a second-stage workflow.
- The script intentionally avoids Redis / Celery / database dependencies so it
  can be run directly from the command line.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV = REPO_ROOT / "backend" / ".env"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "backend" / "outputs"
CHANMAMA_URL = "https://api.chanmama.com/v2/douyin/product/trending"


def load_local_env() -> dict[str, str]:
    """Load env vars from backend/.env without exposing values."""
    values: dict[str, str] = {}
    if not BACKEND_ENV.exists():
        return values

    for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


LOCAL_ENV = load_local_env()


def env_value(key: str, default: str = "") -> str:
    return os.getenv(key, LOCAL_ENV.get(key, default))


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "-"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def pick_value(item: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return default


def normalize(value: float, min_val: float, max_val: float) -> float:
    if max_val <= min_val:
        return 50.0
    return max(0.0, min(100.0, (value - min_val) / (max_val - min_val) * 100.0))


def inverse_normalize(value: float, min_val: float, max_val: float) -> float:
    return 100.0 - normalize(value, min_val, max_val)


def price_fit_score(price: float, min_price: float | None, max_price: float | None) -> float:
    if price <= 0:
        return 50.0
    if min_price is None and max_price is None:
        return 70.0
    if min_price is not None and max_price is not None and min_price <= price <= max_price:
        band_mid = (min_price + max_price) / 2
        band_half = max((max_price - min_price) / 2, 1.0)
        return max(70.0, 100.0 - abs(price - band_mid) / band_half * 30.0)
    if min_price is not None and price < min_price:
        gap = min_price - price
        return max(0.0, 70.0 - gap / max(min_price, 1.0) * 100.0)
    if max_price is not None and price > max_price:
        gap = price - max_price
        return max(0.0, 70.0 - gap / max(max_price, 1.0) * 100.0)
    return 50.0


@dataclass(slots=True)
class Candidate:
    external_id: str
    name: str
    category: str
    price: float
    sales_volume_7d: int
    growth_rate_7d: float
    search_volume: int
    competition_count: int
    avg_competitor_rating: float
    author_count: int
    live_room_count: int
    video_count: int
    score: float = 0.0
    reasons: list[str] | None = None
    penalty_reason: str = ""


@dataclass(slots=True)
class ScoreWeights:
    growth_rate_7d: float = 0.30
    search_volume: float = 0.15
    competition_inverse: float = 0.15
    channel_spread: float = 0.20
    sales_volume_7d: float = 0.10
    price_fit: float = 0.10


async def fetch_chanmama_products(limit: int) -> list[dict[str, Any]]:
    api_key = env_value("CHANMAMA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未检测到 CHANMAMA_API_KEY。请先在 backend/.env 或环境变量中配置后再运行。"
        )

    page_size = min(limit, 50)
    pages = (limit + page_size - 1) // page_size
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        for page in range(1, pages + 1):
            response = await client.get(
                CHANMAMA_URL,
                params={
                    "page": page,
                    "page_size": page_size,
                    "sort_by": "gmv_growth_7d",
                    "sort_order": "desc",
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("data", {}).get("list", [])
            if not items:
                break
            results.extend(items)
            if len(results) >= limit:
                break

    return results[:limit]


def load_input_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [item for item in payload.get("data", {}).get("list", []) if isinstance(item, dict)]
    raise RuntimeError("JSON 文件格式不支持，预期为 list 或包含 data.list 的对象。")


def load_input_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def build_candidates(raw_items: list[dict[str, Any]]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for item in raw_items:
        price = parse_float(
            pick_value(
                item,
                "price",
                "product_price",
                "avg_price",
                "sell_price",
                "sale_price",
                "min_price",
            )
        )

        candidates.append(
            Candidate(
                external_id=str(pick_value(item, "product_id", "id", default="")),
                name=str(pick_value(item, "title", "product_title", "name", default="")),
                category=str(pick_value(item, "category", "category_name", default="未分类")),
                price=price,
                sales_volume_7d=parse_int(pick_value(item, "sales_7d", "sales_volume_7d", default=0)),
                growth_rate_7d=parse_float(
                    pick_value(item, "gmv_growth_7d", "growth_rate_7d", "sales_growth_7d", default=0.0)
                ),
                search_volume=parse_int(pick_value(item, "search_volume", "search_count", default=0)),
                competition_count=parse_int(pick_value(item, "shop_count", "competition_count", default=0)),
                avg_competitor_rating=parse_float(
                    pick_value(item, "avg_rating", "avg_competitor_rating", default=0.0)
                ),
                author_count=parse_int(
                    pick_value(item, "author_count", "influencer_count", "creator_count", default=0)
                ),
                live_room_count=parse_int(
                    pick_value(item, "live_room_count", "room_count", "live_count", default=0)
                ),
                video_count=parse_int(
                    pick_value(item, "video_count", "aweme_count", "content_count", default=0)
                ),
            )
        )
    return candidates


def filter_candidates(
    candidates: list[Candidate],
    category_keyword: str | None,
    min_price: float | None,
    max_price: float | None,
) -> list[Candidate]:
    filtered: list[Candidate] = []
    for candidate in candidates:
        if category_keyword and category_keyword not in candidate.category and category_keyword not in candidate.name:
            continue
        if min_price is not None and candidate.price > 0 and candidate.price < min_price:
            continue
        if max_price is not None and candidate.price > 0 and candidate.price > max_price:
            continue
        filtered.append(candidate)
    return filtered


def score_candidates(
    candidates: list[Candidate],
    min_price: float | None,
    max_price: float | None,
    weights: ScoreWeights,
) -> list[Candidate]:
    if not candidates:
        return []

    growth_min = min(c.growth_rate_7d for c in candidates)
    growth_max = max(c.growth_rate_7d for c in candidates)
    search_min = min(c.search_volume for c in candidates)
    search_max = max(c.search_volume for c in candidates)
    sales_min = min(c.sales_volume_7d for c in candidates)
    sales_max = max(c.sales_volume_7d for c in candidates)
    competition_min = min(c.competition_count for c in candidates)
    competition_max = max(c.competition_count for c in candidates)
    author_min = min(c.author_count for c in candidates)
    author_max = max(c.author_count for c in candidates)
    live_min = min(c.live_room_count for c in candidates)
    live_max = max(c.live_room_count for c in candidates)
    video_min = min(c.video_count for c in candidates)
    video_max = max(c.video_count for c in candidates)

    scored: list[Candidate] = []
    for candidate in candidates:
        growth_score = normalize(candidate.growth_rate_7d, growth_min, growth_max)
        search_score = normalize(candidate.search_volume, search_min, search_max)
        sales_score = normalize(candidate.sales_volume_7d, sales_min, sales_max)
        competition_score = inverse_normalize(
            candidate.competition_count, competition_min, competition_max
        )
        author_score = normalize(candidate.author_count, author_min, author_max)
        live_score = normalize(candidate.live_room_count, live_min, live_max)
        video_score = normalize(candidate.video_count, video_min, video_max)
        spread_score = (author_score + live_score + video_score) / 3
        price_score = price_fit_score(candidate.price, min_price, max_price)

        penalty = 0.0
        penalty_reason = ""
        if candidate.author_count > 0:
            sales_per_author = candidate.sales_volume_7d / max(candidate.author_count, 1)
            if candidate.author_count <= 2 and sales_per_author >= 800:
                penalty = 12.0
                penalty_reason = "达人过于集中，疑似依赖单一达人起量"
        elif candidate.live_room_count <= 1 and candidate.video_count <= 1:
            penalty = 8.0
            penalty_reason = "内容分发面过窄，稳定性偏弱"

        total_score = (
            weights.growth_rate_7d * growth_score
            + weights.search_volume * search_score
            + weights.competition_inverse * competition_score
            + weights.channel_spread * spread_score
            + weights.sales_volume_7d * sales_score
            + weights.price_fit * price_score
            - penalty
        )

        reasons = [
            f"7日增速 {candidate.growth_rate_7d:.1f}%",
            f"搜索量 {candidate.search_volume}",
            f"竞争店铺数 {candidate.competition_count}",
            f"达人/直播/视频 {candidate.author_count}/{candidate.live_room_count}/{candidate.video_count}",
        ]
        if candidate.price > 0:
            reasons.append(f"价格 ¥{candidate.price:.2f}")
        if penalty_reason:
            reasons.append(f"风险: {penalty_reason}")

        candidate.score = round(max(0.0, min(100.0, total_score)), 2)
        candidate.reasons = reasons
        candidate.penalty_reason = penalty_reason
        scored.append(candidate)

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored


def write_outputs(candidates: list[Candidate], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)

    json_payload = [
        {
            **asdict(candidate),
            "reasons": candidate.reasons or [],
        }
        for candidate in candidates
    ]
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "rank",
                "score",
                "name",
                "category",
                "price",
                "sales_volume_7d",
                "growth_rate_7d",
                "search_volume",
                "competition_count",
                "author_count",
                "live_room_count",
                "video_count",
                "penalty_reason",
            ]
        )
        for index, candidate in enumerate(candidates, start=1):
            writer.writerow(
                [
                    index,
                    candidate.score,
                    candidate.name,
                    candidate.category,
                    candidate.price,
                    candidate.sales_volume_7d,
                    candidate.growth_rate_7d,
                    candidate.search_volume,
                    candidate.competition_count,
                    candidate.author_count,
                    candidate.live_room_count,
                    candidate.video_count,
                    candidate.penalty_reason,
                ]
            )


def print_table(candidates: list[Candidate]) -> None:
    print("\nTop20 选品结果")
    print("=" * 120)
    print(
        f"{'排名':<4} {'得分':<6} {'商品名':<28} {'类目':<14} {'价格':<8} "
        f"{'7日增速':<10} {'搜索量':<10} {'店铺数':<8} {'达人/直播/视频':<16}"
    )
    print("-" * 120)
    for idx, item in enumerate(candidates, start=1):
        name = item.name[:26] + ".." if len(item.name) > 28 else item.name
        spread = f"{item.author_count}/{item.live_room_count}/{item.video_count}"
        print(
            f"{idx:<4} {item.score:<6.2f} {name:<28} {item.category[:12]:<14} "
            f"¥{item.price:<7.2f} {item.growth_rate_7d:<10.1f} {item.search_volume:<10} "
            f"{item.competition_count:<8} {spread:<16}"
        )
    print("=" * 120)


async def main() -> int:
    parser = argparse.ArgumentParser(description="蝉妈妈 MVP 自动选品脚本")
    parser.add_argument("--category", default="", help="类目关键词，例如 女装 / 家居 / 防晒")
    parser.add_argument("--min-price", type=float, default=39.0, help="最低价格，默认 39")
    parser.add_argument("--max-price", type=float, default=129.0, help="最高价格，默认 129")
    parser.add_argument("--fetch-limit", type=int, default=200, help="从蝉妈妈抓取的候选数量，默认 200")
    parser.add_argument("--top-n", type=int, default=20, help="输出 topN，默认 20")
    parser.add_argument(
        "--output-prefix",
        default="chanmama_mvp_shortlist",
        help="输出文件名前缀，默认 chanmama_mvp_shortlist",
    )
    parser.add_argument("--input-json", default="", help="直接读取蝉妈妈导出的 JSON 文件")
    parser.add_argument("--input-csv", default="", help="直接读取蝉妈妈导出的 CSV 文件")
    args = parser.parse_args()

    if args.input_json and args.input_csv:
        raise RuntimeError("--input-json 和 --input-csv 只能二选一。")

    if args.input_json:
        raw_items = load_input_json(Path(args.input_json))
    elif args.input_csv:
        raw_items = load_input_csv(Path(args.input_csv))
    else:
        raw_items = await fetch_chanmama_products(limit=args.fetch_limit)

    candidates = build_candidates(raw_items)
    candidates = filter_candidates(
        candidates,
        category_keyword=args.category or None,
        min_price=args.min_price,
        max_price=args.max_price,
    )

    if not candidates:
        raise RuntimeError("筛选后没有候选商品，请放宽类目或价格带。")

    ranked = score_candidates(
        candidates,
        min_price=args.min_price,
        max_price=args.max_price,
        weights=ScoreWeights(),
    )[: args.top_n]

    output_dir = DEFAULT_OUTPUT_DIR
    json_path = output_dir / f"{args.output_prefix}.json"
    csv_path = output_dir / f"{args.output_prefix}.csv"
    write_outputs(ranked, json_path=json_path, csv_path=csv_path)
    print_table(ranked)

    print("\n输出文件:")
    print(f"- {json_path}")
    print(f"- {csv_path}")
    print("\n说明:")
    print("- 当前脚本完成的是蝉妈妈初筛 top20。")
    print("- 毛利维度要做成真实结果，还需要补 1688 API key 走二筛核价。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except httpx.HTTPStatusError as exc:
        print(
            f"蝉妈妈 API 请求失败: HTTP {exc.response.status_code} - {exc.response.text[:300]}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"执行失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
