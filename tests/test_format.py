from nwafu_mcp import format


def test_build_official_report():
    items = [
        {
            "title": "关于举办XX竞赛的通知",
            "url": "https://www.nwsuaf.edu.cn/a.htm",
            "date": "2026-08-26",
            "source": "西北农林科技大学新闻网",
            "snippet": "报名截止8月31日。",
            "category": "通知",
        }
    ]
    report = format.build_official_report(
        {"category": "通知", "keyword": "竞赛", "days": 90}, items
    )
    assert "关于举办XX竞赛的通知" in report
    assert "[查看原文](https://www.nwsuaf.edu.cn/a.htm)" in report
    assert "报名截止8月31日" in report
    assert "时效性提示" in report


def test_build_channel_report_empty():
    report = format.build_channel_report(
        {"window_hours": 72, "post_count": 0, "guild_id": "inwafu1934"}, [], {}, []
    )
    assert "近期暂无新帖" in report


def test_build_channel_report():
    item = {
        "title": "关于奖学金评选的通知",
        "content": "评选时间安排详见正文。",
        "like_count": 12,
        "comment_count": 3,
        "publish_time": 1787815395,
        "source_url": "https://pd.qq.com/g/inwafu1934/post/B_1",
        "author": "某同学",
    }
    report = format.build_channel_report(
        {"window_hours": 72, "post_count": 1, "guild_id": "inwafu1934"},
        [item],
        {"通知": [item]},
        [item],
    )
    assert "热度榜" in report
    assert "重点信息" in report
    assert "[关于奖学金评选的通知](https://pd.qq.com/g/inwafu1934/post/B_1)" in report


def test_md_link_sanitize():
    out = format.md_link("带[方括号]的标题", "http://x")
    assert "【方括号】" in out
    assert "[方括号]" not in out
    assert format.md_link("标题", "http://x").startswith("[标题](")
