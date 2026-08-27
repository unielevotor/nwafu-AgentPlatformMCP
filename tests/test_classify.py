from nwafu_mcp import classify


def test_classify_priority():
    assert classify.classify("关于举办2026年创新创业大赛的通知")[0] == "竞赛"
    assert classify.classify("周末去听学术讲座，欢迎报名")[0] == "活动"
    assert classify.classify("国庆放假安排通知")[0] == "通知"
    assert classify.classify("求推荐好用的防晒霜")[0] == "求助"
    assert classify.classify("这家店真的好吃，强烈安利")[0] == "推荐"
    assert classify.classify("避雷指南：开学必看的宿舍攻略")[0] == "贴士"
    assert classify.classify("今天天气不错")[0] == "其他"


def test_hot_score():
    assert classify.hot_score({"like_count": 10, "comment_count": 3}) == 16
    assert classify.hot_score({"like_count": 0, "comment_count": 0}) == 0


def test_is_important():
    assert classify.is_important({"title": "关于选课的通知", "content": ""})
    assert not classify.is_important({"title": "今天食堂的饭不错", "content": ""})


def test_group_by_category():
    items = [
        {"title": "XX竞赛报名", "content": "", "like_count": 5, "comment_count": 2},
        {"title": "XX讲座", "content": "", "like_count": 1, "comment_count": 0},
        {"title": "XX比赛", "content": "", "like_count": 9, "comment_count": 3},
        {"title": "求问校车时刻", "content": "", "like_count": 0, "comment_count": 4},
    ]
    groups = classify.group_by_category(items)
    assert set(groups) == {"竞赛", "活动", "求助"}
    assert groups["竞赛"][0]["title"] == "XX比赛"
