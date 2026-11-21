"""Run an ephemeral, loopback-only IGDB review card (never public API/DB)."""

import argparse
from getpass import getpass

from app.trend_collection.igdb_client import IgdbClient
from app.trend_collection.igdb_local_preview import (
    build_local_review_html,
    build_local_review_json,
    serve_loopback,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    try:
        client_id = input("IGDB Client ID (입력 내용은 화면에 보입니다): ").strip()
        client_secret = getpass("IGDB Client Secret (화면 표시 안 함): ")
        if not client_id or not client_secret:
            raise ValueError("CREDENTIALS_MISSING")

        def make_client():
            return IgdbClient(client_id, client_secret)

        def render():
            return build_local_review_html(make_client)

        def render_json():
            return build_local_review_json(make_client)

        with serve_loopback(
            render, port=args.port, render_json=render_json,
        ) as server:
            port = server.server_port
            print(
                f"개발 전용 IGDB TrendCard: http://127.0.0.1:{port}/"
                " (Ctrl+C 종료 / 파일·DB 저장 없음)"
            )
            try:
                server.serve_forever(poll_interval=0.2)
            except KeyboardInterrupt:
                pass
        return 0
    except Exception:
        # No exception details, access token, upstream payload or secret.
        print("IGDB 내부 미리보기를 시작하지 못했습니다.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
