"""Local, ephemeral IGDB review card. No API route, DB or publication rights."""

from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from time import sleep

from app.trend_collection.igdb_adapter import SOURCE_URL, IgdbReviewAdapter
from app.trend_collection.igdb_supply_snapshot import (
    UNBOUND,
    IgdbSnapshotBridge,
)
from app.trend_collection.publication_policy import PopularitySnapshot

_STYLE = """
body { margin:0; padding:36px 16px; background:#f3f6fa;
       font-family:system-ui,sans-serif; color:#172234; }
main { max-width:550px; margin:auto; }
.card { background:white; border:1px solid #d5deeb; border-radius:14px;
        padding:22px; box-shadow:0 3px 14px #17223412; }
.flag { font-size:13px; color:#8b4215; font-weight:700; }
.title { font-size:24px; margin:14px 0 8px; overflow-wrap:anywhere; }
.summary { line-height:1.6; overflow-wrap:anywhere; }
.category { display:inline-block; background:#e8f0fc; border-radius:8px;
            padding:7px 10px; font-size:14px; margin:8px 0; }
.meta { color:#536178; font-size:13px; }
.link { display:inline-block; margin-top:14px; padding:11px 16px;
        border:1px solid #8a9cb5; border-radius:8px; color:#184779; }
.notice { font-size:13px; color:#667085; line-height:1.6; margin-top:16px; }
"""


def _page(body: str) -> str:
    return (
        '<!doctype html><html lang="ko"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>IGDB 내부 검토 미리보기</title>'
        f'<style>{_STYLE}</style></head><body><main>'
        '<h1>IGDB 임시 TrendCard</h1>'
        f'{body}'
        '<p class="notice">개발·내부 검토 전용. 실제 Trend Leader 게시물,'
        ' 인기 검색 순위, 운영 승인 또는 데이터 이용 허가를 의미하지 않습니다.'
        ' 페이지 데이터는 서버에서 파일·DB에 저장하지 않습니다.</p>'
        '</main></body></html>'
    )


def _card(snapshot: PopularitySnapshot) -> str:
    if (
        type(snapshot) is not PopularitySnapshot
        or snapshot.target != UNBOUND
        or snapshot.platform != "ETC"
        or snapshot.parent_code != "GAME"
        or snapshot.child_name not in {"PC 게임", "모바일 게임", "콘솔 게임"}
        or snapshot.metric_id != 1
        or not isinstance(snapshot.source_url, str)
        or SOURCE_URL.fullmatch(snapshot.source_url) is None
        or type(snapshot.rank) is not int
        or not 1 <= snapshot.rank <= 20
    ):
        raise ValueError("REVIEW_SNAPSHOT_INVALID")
    title = escape(snapshot.title, quote=True)
    summary = escape(snapshot.summary, quote=True)
    child = escape(snapshot.child_name, quote=True)
    url = escape(snapshot.source_url, quote=True)
    calculated = escape(snapshot.calculated_at_utc, quote=True)
    return _page(
        '<article class="card">'
        '<div class="flag">미게시 · 독립 검증 완료</div>'
        f'<h2 class="title">{title}</h2>'
        f'<p class="summary">{summary}</p>'
        f'<div class="category">게임 · {child}</div>'
        f'<p class="meta">IGDB Visits 관측 {snapshot.rank}위 · '
        f'관측 기준 {calculated}</p>'
        '<p class="meta">출처: IGDB (게임 페이지 방문 기반 지표)</p>'
        f'<a class="link" href="{url}" target="_blank"'
        ' rel="noopener noreferrer" referrerpolicy="no-referrer">'
        'IGDB 원문 보기</a>'
        '</article>'
    )


def build_local_review_html(client_factory, *, clock=None, after_game_id=None,
                            between_clients=sleep):
    """Two isolated API clients: collect -> independent verify -> memory-only UI."""
    now = clock if clock is not None else lambda: datetime.now(timezone.utc)
    first = IgdbReviewAdapter(client_factory().query)
    preview = first.collect_review(now(), after_game_id=after_game_id)
    if preview is None:
        return _page(
            '<article class="card"><p>현재 정책에서 적격 후보가 없습니다.'
            '</p><p class="meta">DB 저장이나 Writer 실행은 없습니다.</p>'
            '</article>'
        )
    between_clients(0.5)
    independently_verified = IgdbSnapshotBridge(
        client_factory().query,
    ).verify(preview, now())
    return _card(independently_verified)


def local_handler(render_page):
    """Factory for a loopback-only HTTP handler with no persistent cache."""

    class LocalPreviewHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers.get("Host", "")
            if host not in {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }:
                self.send_error(400, "Invalid Host")
                return
            if self.path != "/":
                self.send_error(404, "Not Found")
                return
            try:
                html = render_page().encode("utf-8")
                status = 200
            except Exception:
                # No raw IGDB response, exception text or credentials in HTML.
                html = _page(
                    '<article class="card"><p>IGDB 내부 검토를 완료하지 '
                    '못했습니다.</p><p>외부 API 상태와 정책을 확인해 주세요.'
                    '</p></article>'
                ).encode("utf-8")
                status = 503
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, format, *args):
            # Do not record user-agent, query, source payload or credentials.
            return

    return LocalPreviewHandler


def serve_loopback(render_page, *, port=0):
    """Caller owns server lifetime; accepts no non-loopback bind argument."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("INVALID_PREVIEW_PORT")
    return HTTPServer(("127.0.0.1", port), local_handler(render_page))
