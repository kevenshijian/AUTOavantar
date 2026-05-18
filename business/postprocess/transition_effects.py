"""
转场效果常量定义
定义 FFmpeg xfade 滤镜支持的转场效果映射表
"""

from typing import Dict, List, Tuple

# 转场效果映射表（中文分类 → 效果列表）
TRANSITION_EFFECTS: Dict[str, List[Dict[str, str]]] = {
    "淡入淡出": [
        {"name": "交叉淡入淡出", "value": "fade"},
        {"name": "渐隐至黑", "value": "fadeblack"},
        {"name": "渐隐至白", "value": "fadewhite"},
        {"name": "溶解", "value": "dissolve"},
        {"name": "距离过渡", "value": "distance"},
    ],
    "滑动擦除": [
        {"name": "向左滑动", "value": "slideleft"},
        {"name": "向右滑动", "value": "slideright"},
        {"name": "向上滑动", "value": "slideup"},
        {"name": "向下滑动", "value": "slidedown"},
        {"name": "向左擦除", "value": "wipeleft"},
        {"name": "向右擦除", "value": "wiperight"},
        {"name": "向上擦除", "value": "wipeup"},
        {"name": "向下擦除", "value": "wipedown"},
        {"name": "平滑左滑", "value": "smoothleft"},
        {"name": "平滑右滑", "value": "smoothright"},
        {"name": "平滑上滑", "value": "smoothup"},
        {"name": "平滑下滑", "value": "smoothdown"},
    ],
    "图形变换": [
        {"name": "圆形裁剪", "value": "circlecrop"},
        {"name": "矩形裁剪", "value": "rectcrop"},
        {"name": "圆形展开", "value": "circleopen"},
        {"name": "圆形闭合", "value": "circleclose"},
        {"name": "水平展开", "value": "horzopen"},
        {"name": "水平闭合", "value": "horzclose"},
        {"name": "垂直展开", "value": "vertopen"},
        {"name": "垂直闭合", "value": "vertclose"},
        {"name": "放大过渡", "value": "zoomin"},
        {"name": "水平挤压", "value": "squeezeh"},
        {"name": "垂直挤压", "value": "squeezev"},
    ],
    "特效切片": [
        {"name": "像素化", "value": "pixelize"},
        {"name": "径向过渡", "value": "radial"},
        {"name": "高斯模糊", "value": "hblur"},
        {"name": "水平左切片", "value": "hlslice"},
        {"name": "水平右切片", "value": "hrslice"},
        {"name": "垂直上切片", "value": "vuslice"},
        {"name": "垂直下切片", "value": "vdslice"},
    ],
}

# 所有转场效果的英文标识列表（用于随机选择）
ALL_TRANSITION_EFFECTS: List[str] = [
    # 淡入淡出类
    "fade", "fadeblack", "fadewhite", "dissolve", "distance",
    # 滑动擦除类
    "slideleft", "slideright", "slideup", "slidedown",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    # 图形变换类
    "circlecrop", "rectcrop", "circleopen", "circleclose",
    "horzopen", "horzclose", "vertopen", "vertclose",
    "zoomin", "squeezeh", "squeezev",
    # 特效切片类
    "pixelize", "radial", "hblur",
    "hlslice", "hrslice", "vuslice", "vdslice",
]

# 转场分类列表
TRANSITION_CATEGORIES: List[str] = list(TRANSITION_EFFECTS.keys())


def is_valid_transition_effect(effect: str) -> bool:
    """
    检查转场效果是否有效

    Args:
        effect: 转场效果名称（英文标识）

    Returns:
        是否为有效的转场效果
    """
    return effect in ALL_TRANSITION_EFFECTS


def get_transition_effects_by_category(category: str) -> List[Dict[str, str]]:
    """
    根据分类获取转场效果列表

    Args:
        category: 分类名称（中文）

    Returns:
        该分类下的转场效果列表
    """
    return TRANSITION_EFFECTS.get(category, [])


def get_all_transition_effects() -> Dict[str, List[Dict[str, str]]]:
    """
    获取所有转场效果

    Returns:
        按分类组织的转场效果字典
    """
    return TRANSITION_EFFECTS


def get_effect_name_by_value(value: str) -> str:
    """
    根据英文标识获取中文名称

    Args:
        value: 转场效果英文标识

    Returns:
        中文名称，如果未找到则返回英文标识
    """
    for category, effects in TRANSITION_EFFECTS.items():
        for effect in effects:
            if effect["value"] == value:
                return effect["name"]
    return value
