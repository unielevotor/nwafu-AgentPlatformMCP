from nwafu_mcp.server import _derive_keywords, _match_channel_items


def test_derive_keywords_scholarship():
    kws = _derive_keywords("最近有没有奖学金评选通知")
    assert any("奖学金" in k for k in kws)
    assert "最近" not in kws
    assert len(kws) <= 3


def test_derive_keywords_plain():
    kws = _derive_keywords("植保学院最近有什么讲座")
    assert kws
    assert all(len(k) >= 2 for k in kws)


def test_match_channel_items_keyword():
    feeds = [
        {
            "title": "关于奖学金评选的通知",
            "content": "奖学金评选即将开始",
            "like_count": 3,
            "comment_count": 1,
            "publish_time": 1787815395,
            "source_url": "http://x",
        },
        {
            "title": "今天食堂的饭不错",
            "content": "红烧肉很好吃",
            "like_count": 0,
            "comment_count": 0,
            "publish_time": 1787815395,
            "source_url": "http://y",
        },
    ]
    result = _match_channel_items(feeds, "奖学金评选", ["奖学金", "评选"], limit=10)
    assert len(result) == 1
    assert result[0]["title"] == "关于奖学金评选的通知"


def test_match_channel_items_no_keywords_falls_back_bigram():
    feeds = [
        {
            "title": "校车时刻表",
            "content": "北校到南校的校车",
            "like_count": 1,
            "comment_count": 0,
            "publish_time": 1787815395,
            "source_url": "http://x",
        }
    ]
    result = _match_channel_items(feeds, "校车时间", [], limit=10)
    assert len(result) == 1
