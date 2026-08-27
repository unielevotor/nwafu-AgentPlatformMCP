from nwafu_mcp import official_site


SAMPLE_PAGE = """
<html><body>
<div id="searchResultList">
<ul class="Listheight">
<li>
  <div class="search01">
    <a href="https&#x3a;&#x2f;&#x2f;ppc.nwafu.edu.cn&#x2f;xzbg&#x2f;1fb393b7d6504e06aa185f0afb31d6af.htm" target="_blank">
      <h2>关于举办2026年植保论坛系列学术报告会（十七）的通知&nbsp;-[链]</h2>
    </a>
    <span><label>2026&#x5e74;08&#x6708;26&#x65e5;</label>
      <label>&#x897f;&#x5317;&#x519c;&#x6797;&#x79d1;&#x6280;&#x5927;&#x5b66;&#x690d;&#x7269;&#x4fdd;&#x62a4;&#x5b66;&#x9662;</label><br></span>
    <span>https&#x3a;&#x2f;&#x2f;ppc.nwafu.edu.cn&#x2f;xzbg&#x2f;1fb393b7d6504e06aa185f0afb31d6af.htm</span>
    <p>报告会将于8月27日举行，欢迎广大师生参加。</p>
  </div>
</li>
</ul>
</div>
</body></html>
"""


def test_parse_search_page():
    items = official_site._parse_search_page(SAMPLE_PAGE)
    assert len(items) == 1
    it = items[0]
    assert it["title"] == "关于举办2026年植保论坛系列学术报告会（十七）的通知"
    assert it["url"].startswith("https://ppc.nwafu.edu.cn/")
    assert it["date"] == "2026-08-26"
    assert "植物保护学院" in it["source"]
    assert "8月27日" in it["snippet"]


def test_normalize_category():
    assert official_site.normalize_category("讲座") == "活动"
    assert official_site.normalize_category("比赛") == "竞赛"
    assert official_site.normalize_category("公告") == "通知"
    assert official_site.normalize_category("随便") == "全部"


def test_days_ok():
    import datetime

    today = datetime.date.today()
    old = (today - datetime.timedelta(days=120)).strftime("%Y-%m-%d")
    recent = today.strftime("%Y-%m-%d")
    assert official_site._days_ok(recent, 90)
    assert not official_site._days_ok(old, 90)
