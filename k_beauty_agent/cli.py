from __future__ import annotations

import argparse
from pathlib import Path

from .agent import KBeautyAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Explainable K-beauty recommendation agent")
    parser.add_argument("query", help="User request, e.g. '지성 피부에 맞는 기초 제품을 추천해줘'")
    parser.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parents[1] / "data" / "sample_products.json"),
        help="Path to product JSON database",
    )
    parser.add_argument("--limit", type=int, default=3, help="Number of recommendations")
    args = parser.parse_args()

    agent = KBeautyAgent.from_json(args.db)
    print(agent.answer(args.query, limit=args.limit))


if __name__ == "__main__":
    main()
