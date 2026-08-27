# -*- coding: utf-8 -*-
"""帖子分类与热度评分（规则引擎，纯本地、零依赖）。

分类优先级（同时命中多个关键词时取先匹配的类别）：
  竞赛 > 活动 > 通知 > 求助 > 推荐 > 贴士 > 其他
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# 类别 -> 命中关键词（按优先级排列）
RULES: Dict[str, List[str]] = {
    "竞赛": [
        "竞赛", "比赛", "大赛", "挑战赛", "选拔赛", "初赛", "复赛", "决赛",
        "创新创业大赛", "答辩", "获奖名单", "晋级", "参赛",
    ],
    "活动": [
        "活动", "讲座", "论坛", "沙龙", "报告会", "宣讲", "招募", "志愿者",
        "报名", "晚会", "演出", "音乐会", "展览", "观影", "运动会", "校庆",
        "迎新", "招新", "社团", "团建", "实践", "参观",
    ],
    "通知": [
        "通知", "公告", "公示", "截止", "变更", "安排", "放假", "停水",
        "停电", "停网", "关闭", "开放时间", "注意事项", "结果公布",
    ],
    "求助": [
        "求助", "求问", "求推荐", "求分享", "有没有", "有没有人", "学长学姐",
        "帮帮", "急", "问一下", "谁知道", "求解答", "求推荐", "应该怎么办",
    ],
    "推荐": [
        "推荐", "安利", "种草", "测评", "探店", "好吃", "好喝", "好用",
        "必去", "值得", "强推", "宝藏", "绝绝子", "打卡",
    ],
    "贴士": [
        "避雷", "攻略", "技巧", "经验", "小贴士", "盘点", "总结", "防坑",
        "干货", "流程", "时间线", "怎么做", "怎么弄", "如何办理", "提醒",
    ],
}

# 重要信息标记词（标题/正文命中则进"重点提示"）
IMPORTANT_KEYWORDS = [
    "通知", "公告", "紧急", "截止", "报名", "即日", "安全", "停水", "停电",
    "放假", "考试", "成绩", "选课", "缴费", "补助", "奖学金", "评优",
    "官方", "党委", "团委", "教务处", "研究生院", "保卫",
]

CATEGORY_ORDER = ["竞赛", "活动", "通知", "求助", "推荐", "贴士"]


def classify(text: str) -> Tuple[str, List[str]]:
    """返回 (主类别, 命中标签列表)。未命中返回 "其他"。"""
    if not text:
        return "其他", []
    tags: List[str] = []
    for cat, keywords in RULES.items():
        for kw in keywords:
            if kw in text:
                tags.append(kw)
                return cat, tags
    return "其他", tags


def hot_score(item: Dict[str, Any]) -> int:
    """热度分：点赞 + 评论加权。评论权重更高（互动深度）。"""
    likes = int(item.get("like_count") or 0)
    comments = int(item.get("comment_count") or 0)
    return likes + 2 * comments


def is_important(item: Dict[str, Any]) -> bool:
    text = f"{item.get('title') or ''} {item.get('content') or ''}"
    return any(kw in text for kw in IMPORTANT_KEYWORDS)


def group_by_category(
    items: List[Dict[str, Any]],
    per_category: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """按主类别分组；组内按热度分降序。"""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        cat, _ = classify(f"{item.get('title') or ''} {item.get('content') or ''}")
        groups.setdefault(cat, []).append(item)
    for cat in groups:
        groups[cat].sort(key=hot_score, reverse=True)
        groups[cat] = groups[cat][:per_category]
    return groups
