from __future__ import annotations

from datetime import datetime

from app.core.config import Settings
from app.services.weread_digest import WeReadDigestService


def build_service(tmp_path) -> WeReadDigestService:
    settings = Settings(
        WEREAD_MARKDOWN_OUTPUT_DIR=str(tmp_path),
        WEREAD_COOKIE_HEADER="wr_vid=dummy;",
    )
    return WeReadDigestService(settings=settings)


def test_resolve_window_uses_previous_completed_9am_window(tmp_path):
    service = build_service(tmp_path)

    start, end = service.resolve_window(now=datetime(2026, 6, 26, 8, 30))

    assert start.isoformat() == "2026-06-24T09:00:00+08:00"
    assert end.isoformat() == "2026-06-25T09:00:00+08:00"


def test_write_markdown_uses_title_and_summary_link_format(tmp_path):
    service = build_service(tmp_path)
    digest = {
        "window": {
            "timezone": "Asia/Shanghai",
            "start_iso": "2026-06-25T09:00:00+08:00",
            "end_iso": "2026-06-26T09:00:00+08:00",
            "start_label": "2026-06-25_09",
            "end_label": "2026-06-26_09",
        },
        "refreshed_at": "2026-06-26T09:05:00+08:00",
        "total_sources": 1,
        "total_articles": 1,
        "sources": [
            {
                "id": "xinzhiyuan",
                "name": "新智元",
                "book_id": "MP_WXS_123",
                "article_count": 1,
                "status": "ok",
                "last_error": None,
            }
        ],
        "items": [
            {
                "id": "item-1",
                "review_id": "review-1",
                "title": "原标题",
                "source_id": "xinzhiyuan",
                "source_name": "新智元",
                "url": "https://weread.qq.com/web/mp/content?reviewId=review-1",
                "published_at": "2026-06-25T12:00:00+08:00",
                "published_label": "2026-06-25 12:00",
                "summary": "文章概述了模型能力与商业化进展。",
                "excerpt": "节选",
            }
        ],
        "notes": [],
    }

    output_path = service._write_markdown(digest)
    content = output_path.read_text(encoding="utf-8")

    assert "## 新智元" in content
    assert "- 2026-06-25 12:00 | 原标题" in content
    assert "[文章概述了模型能力与商业化进展。](https://weread.qq.com/web/mp/content?reviewId=review-1)" in content
    assert "总计 1 篇。" in content


def test_summarize_text_prefers_first_informative_sentence(tmp_path):
    service = build_service(tmp_path)

    summary = service._summarize_text("这篇文章详细分析了多模态模型在端侧落地时的算力约束与产品取舍。随后又补充了案例。")

    assert summary == "这篇文章详细分析了多模态模型在端侧落地时的算力约束与产品取舍。"


def test_extract_original_article_url_from_weread_html(tmp_path):
    service = build_service(tmp_path)
    html = '''
    <script>
      var msg_link = "https://mp.weixin.qq.com/s?__biz=MzI3MTA0MTk1MA==\\x26mid=2652709101\\x26idx=3\\x26sn=abcdef\\x26chksm=123456";
    </script>
    '''

    url = service._extract_original_article_url(html)

    assert url == "https://mp.weixin.qq.com/s?__biz=MzI3MTA0MTk1MA==&mid=2652709101&idx=3&sn=abcdef&chksm=123456"
