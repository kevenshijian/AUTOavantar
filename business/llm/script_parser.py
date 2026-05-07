"""
文案解析器模块
将 JSON 格式的文案解析为结构化的 ScriptSegment 列表
支持单人和双人模式
情绪向量参数统一从 voicel/emotion_mapping.yaml 加载
"""

import json
import logging
import os
import yaml
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from pathlib import Path

from core.models.task import ScriptSegment, SceneType, EmotionType

logger = logging.getLogger(__name__)

# 情绪映射配置（从 voicel/emotion_mapping.yaml 加载）
_EMOTION_MAPPING_CACHE: Dict[str, Dict] = {}


def _load_emotion_mapping() -> Dict[str, Dict]:
    """
    从 voicel/emotion_mapping.yaml 加载情绪映射配置
    这是情绪向量参数的唯一来源

    Returns:
        情绪名称到参数配置的映射
    """
    global _EMOTION_MAPPING_CACHE

    if _EMOTION_MAPPING_CACHE:
        return _EMOTION_MAPPING_CACHE

    # 查找 voicel 目录下的 emotion_mapping.yaml
    project_root = Path(__file__).parent.parent.parent
    voicel_dir = project_root / "voicel"

    mapping_path = voicel_dir / "emotion_mapping.yaml"

    if not mapping_path.exists():
        logger.warning(f"未找到情绪映射文件: {mapping_path}")
        return {}

    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        _EMOTION_MAPPING_CACHE = config
        logger.info(f"已加载情绪映射配置: {mapping_path}, 共 {len(config)} 种情绪")
        return config
    except Exception as e:
        logger.error(f"加载情绪映射文件失败: {e}")
        return {}


def _parse_json_script(script_text: str) -> List[Tuple[str, Any]]:
    """
    解析 JSON 文案
    
    使用 object_pairs_hook 保留所有键值对，包括重复的标签键。
    这样当文案中有多个相同标签的分段时，不会丢失任何分段。
    
    Args:
        script_text: JSON 格式的文案
        
    Returns:
        List[Tuple[str, Any]]: 键值对列表，保留所有重复键
    """
    def preserve_pairs(pairs):
        """保留所有键值对，包括重复键"""
        return pairs
    
    try:
        decoder = json.JSONDecoder(object_pairs_hook=preserve_pairs)
        result = decoder.decode(script_text)
        return result
    except json.JSONDecodeError as e:
        raise e


class ScriptMode(Enum):
    """文案模式"""
    SINGLE = "single"     # 单人模式
    DOUBLE = "double"     # 双人模式
    UNKNOWN = "unknown"    # 未知模式


class EmotionParams:
    """情绪参数数据类"""
    def __init__(self, vec1=0.0, vec2=0.0, vec3=0.0, vec4=0.0, 
                 vec5=0.0, vec6=0.0, vec7=0.0, vec8=0.0):
        self.vec1 = vec1
        self.vec2 = vec2
        self.vec3 = vec3
        self.vec4 = vec4
        self.vec5 = vec5
        self.vec6 = vec6
        self.vec7 = vec7
        self.vec8 = vec8
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "vec1": self.vec1, "vec2": self.vec2, "vec3": self.vec3, "vec4": self.vec4,
            "vec5": self.vec5, "vec6": self.vec6, "vec7": self.vec7, "vec8": self.vec8
        }


# 场景标签映射
SCENE_CONFIG = {
    "开场": SceneType.OPENING,
    "结束": SceneType.ENDING,
    "封面总结": SceneType.OPENING,
}


class EmotionLabel(Enum):
    """情绪标签映射（向后兼容，用于获取 EmotionType）"""
    开场 = EmotionType.CALM
    兴奋 = EmotionType.SURPRISE
    开心 = EmotionType.JOY
    惊喜 = EmotionType.SURPRISE
    激动 = EmotionType.JOY
    产品展示 = EmotionType.CALM
    环境展示 = EmotionType.CALM
    细节展示 = EmotionType.CALM
    冷静 = EmotionType.CALM
    平淡 = EmotionType.CALM
    功能介绍 = EmotionType.CALM
    使用效果 = EmotionType.CALM
    高兴 = EmotionType.JOY
    生气 = EmotionType.ANGER
    伤心 = EmotionType.SADNESS
    害怕 = EmotionType.FEAR
    厌恶 = EmotionType.DISGUST
    低落 = EmotionType.DEPRESSION
    结束 = EmotionType.CALM


class SceneLabel(Enum):
    """场景标签映射"""
    开场 = SceneType.OPENING
    结束 = SceneType.ENDING
    封面总结 = SceneType.OPENING


class ScriptParser:
    """文案解析器"""

    def __init__(self):
        """初始化解析器"""
        self.logger = logging.getLogger(__name__)

    def detect_mode(self, parsed_pairs: Union[Dict, List[Tuple[str, Any]]]) -> ScriptMode:
        """
        检测文案模式（单人/双人）

        Args:
            parsed_pairs: 解析后的键值对列表或字典

        Returns:
            ScriptMode: 文案模式
        """
        # 统一转换为列表格式处理
        if isinstance(parsed_pairs, dict):
            pairs = list(parsed_pairs.items())
        else:
            pairs = parsed_pairs
        
        has_double_speaker = False
        for key, value in pairs:
            if isinstance(value, list):
                for item in value:
                    # item 可能是 dict 或 List[Tuple]（使用 object_pairs_hook 时）
                    if isinstance(item, dict):
                        if "左边说话人" in item or "右边说话人" in item:
                            has_double_speaker = True
                            break
                        elif "左边" in item or "右边" in item:
                            has_double_speaker = True
                            break
                    elif isinstance(item, list):
                        # object_pairs_hook 将嵌套对象转为 List[Tuple]
                        for sub_key, sub_value in item:
                            if sub_key in ("左边说话人", "右边说话人", "左边", "右边"):
                                has_double_speaker = True
                                break
                        if has_double_speaker:
                            break
                if has_double_speaker:
                    break
        
        if has_double_speaker:
            return ScriptMode.DOUBLE
        
        return ScriptMode.SINGLE

    def get_emotion_from_label(self, label: str) -> EmotionType:
        """
        从标签获取情绪类型

        Args:
            label: 标签名称

        Returns:
            EmotionType: 情绪类型，默认为平静
        """
        if label in EmotionLabel.__members__:
            emotion_enum = EmotionLabel[label]
            return emotion_enum.value if hasattr(emotion_enum, 'value') else EmotionType.CALM
        return EmotionType.CALM

    def get_emotion_params_from_label(self, label: str) -> EmotionParams:
        """
        从标签获取情绪参数（vec1-vec8）
        从 voicel/emotion_mapping.yaml 读取（唯一来源）

        Args:
            label: 标签名称

        Returns:
            EmotionParams: 情绪参数对象
        """
        emotion_mapping = _load_emotion_mapping()

        if label in emotion_mapping:
            params = emotion_mapping[label]
            if isinstance(params, dict):
                return EmotionParams(
                    vec1=params.get("vec1", 0.0),
                    vec2=params.get("vec2", 0.0),
                    vec3=params.get("vec3", 0.0),
                    vec4=params.get("vec4", 0.0),
                    vec5=params.get("vec5", 0.0),
                    vec6=params.get("vec6", 0.0),
                    vec7=params.get("vec7", 0.0),
                    vec8=params.get("vec8", 0.0)
                )

        return EmotionParams()  # 默认全部0.0
    
    def get_scene_from_label(self, label: str, default_scene: SceneType = SceneType.LOOP) -> SceneType:
        """
        从标签获取场景类型
        
        Args:
            label: 标签名称
            default_scene: 默认场景类型
            
        Returns:
            SceneType: 场景类型
        """
        if label in SCENE_CONFIG:
            return SCENE_CONFIG[label]
        # 检查是否是场景类型标签
        if label in ["环境展示", "产品展示", "细节展示", "功能介绍", "使用效果"]:
            return SceneType.SCENE
        return default_scene
    
    def is_scene_label(self, label: str) -> bool:
        """
        判断是否为场景标签（不需要情绪参数）
        从 voicel/emotion_mapping.yaml 动态判断

        Args:
            label: 标签名称

        Returns:
            bool: 是否为场景标签
        """
        # 场景标签列表（从 emotion_mapping.yaml 中的标签推断）
        # 这些标签主要用于场景描述，情绪表达较弱
        scene_labels = ["环境展示", "产品展示", "细节展示", "功能介绍", "使用效果", "开场", "结束", "旁白视角"]
        return label in scene_labels

    def parse_single_script(self, parsed_pairs: Union[Dict, List[Tuple[str, Any]]]) -> List[ScriptSegment]:
        """
        解析单人文案
        
        Args:
            parsed_pairs: 解析后的键值对列表或字典
            
        Returns:
            List[ScriptSegment]: 文案段落列表
        """
        segments = []
        segment_index = 0

        # 统一转换为列表格式处理，保留所有重复键
        if isinstance(parsed_pairs, dict):
            pairs = list(parsed_pairs.items())
        else:
            pairs = parsed_pairs
            
        for label, content in pairs:
            if not content:
                continue

            if label == "封面总结":
                continue

            if isinstance(content, str):
                scene_type = self.get_scene_from_label(label, SceneType.LOOP)
                emotion = self.get_emotion_from_label(label)
                # 获取情绪参数
                emotion_params = self.get_emotion_params_from_label(label)
                # 判断是否为场景标签（场景标签不需要情绪参数）
                is_scene = self.is_scene_label(label)
                
                segments.append(ScriptSegment(
                    segment_id=f"seg_{segment_index:03d}",
                    text=content,
                    scene_type=scene_type,
                    emotion=emotion,
                    tone=label,
                    emotion_weight=0.0 if is_scene else 0.4,  # 场景标签不添加情绪权重
                    tone_weight=0.2,
                    speaker="single"
                ))
                # 将情绪参数存储到segment的元数据中
                segment = segments[-1]
                segment.emotion_params = emotion_params.to_dict() if not is_scene else {}
                segment.is_scene_label = is_scene
                
                segment_index += 1

        return segments

    def parse_double_script(self, parsed_pairs: Union[Dict, List[Tuple[str, Any]]]) -> List[ScriptSegment]:
        """
        解析双人文案
        
        Args:
            parsed_pairs: 解析后的键值对列表或字典
            
        Returns:
            List[ScriptSegment]: 文案段落列表
        """
        segments = []
        segment_index = 0

        # 统一转换为列表格式处理，保留所有重复键
        if isinstance(parsed_pairs, dict):
            pairs = list(parsed_pairs.items())
        else:
            pairs = parsed_pairs
            
        for label, content in pairs:
            if not content:
                continue

            if label == "封面总结":
                continue

            scene_type = self.get_scene_from_label(label, SceneType.LOOP)
            emotion = self.get_emotion_from_label(label)
            # 获取情绪参数
            emotion_params = self.get_emotion_params_from_label(label)
            # 判断是否为场景标签（场景标签不需要情绪参数）
            is_scene = self.is_scene_label(label)
            # 情绪权重
            emotion_weight = 0.0 if is_scene else 0.4

            if isinstance(content, list):
                left_text = None
                right_text = None

                for item in content:
                    # item 可能是 dict 或 List[Tuple]（使用 object_pairs_hook 时）
                    if isinstance(item, dict):
                        if "左边说话人" in item:
                            left_text = item["左边说话人"]
                        elif "右边说话人" in item:
                            right_text = item["右边说话人"]
                        elif "左边" in item:
                            left_text = item["左边"]
                        elif "右边" in item:
                            right_text = item["右边"]
                    elif isinstance(item, list):
                        # object_pairs_hook 将嵌套对象转为 List[Tuple]
                        for sub_key, sub_value in item:
                            if sub_key == "左边说话人" or sub_key == "左边":
                                left_text = sub_value
                            elif sub_key == "右边说话人" or sub_key == "右边":
                                right_text = sub_value

                if left_text:
                    segment = ScriptSegment(
                        segment_id=f"seg_{segment_index:03d}",
                        text=left_text,
                        scene_type=scene_type,
                        emotion=emotion,
                        tone=label,
                        emotion_weight=emotion_weight,
                        tone_weight=0.2,
                        speaker="left"
                    )
                    segment.emotion_params = emotion_params.to_dict() if not is_scene else {}
                    segment.is_scene_label = is_scene
                    segments.append(segment)
                    segment_index += 1

                if right_text:
                    segment = ScriptSegment(
                        segment_id=f"seg_{segment_index:03d}",
                        text=right_text,
                        scene_type=scene_type,
                        emotion=emotion,
                        tone=label,
                        emotion_weight=emotion_weight,
                        tone_weight=0.2,
                        speaker="right"
                    )
                    segment.emotion_params = emotion_params.to_dict() if not is_scene else {}
                    segment.is_scene_label = is_scene
                    segments.append(segment)
                    segment_index += 1

        return segments

    def parse_json_script(self, script_text: str) -> List[ScriptSegment]:
        """
        解析 JSON 格式的文案

        Args:
            script_text: JSON 格式的文案文本

        Returns:
            List[ScriptSegment]: 文案段落列表
        """
        try:
            parsed_pairs = _parse_json_script(script_text)
            mode = self.detect_mode(parsed_pairs)

            self.logger.info(f"JSON 解析成功，检测到模式: {mode.value}")
            
            # 记录所有标签（包括重复的）
            labels = [pair[0] for pair in parsed_pairs]
            label_counts = {}
            for label in labels:
                label_counts[label] = label_counts.get(label, 0) + 1
            self.logger.info(f"文案标签: {labels}, 共 {len(labels)} 个分段")
            if len(label_counts) < len(labels):
                self.logger.info(f"检测到重复标签: {label_counts}")

            if mode == ScriptMode.DOUBLE:
                segments = self.parse_double_script(parsed_pairs)
            else:
                segments = self.parse_single_script(parsed_pairs)

            self.logger.info(f"文案解析完成，共 {len(segments)} 个段落")
            return segments

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析失败: {e}")
            return self.parse_text_script(script_text)

    def parse_text_script(self, script_text: str) -> List[ScriptSegment]:
        """
        解析纯文本格式的文案（简单分割）

        Args:
            script_text: 纯文本格式的文案

        Returns:
            List[ScriptSegment]: 文案段落列表
        """
        segments = []
        sentences = [s.strip() for s in script_text.split("。") if s.strip()]

        for i, sentence in enumerate(sentences):
            if i == 0:
                scene = SceneType.OPENING
            elif i == len(sentences) - 1:
                scene = SceneType.ENDING
            else:
                if any(keyword in sentence for keyword in ["场景", "环境", "地点"]):
                    scene = SceneType.SCENE
                else:
                    scene = SceneType.LOOP

            segments.append(ScriptSegment(
                segment_id=f"seg_{i:03d}",
                text=sentence,
                scene_type=scene,
                emotion=EmotionType.CALM,
                tone="叙述",
                emotion_weight=0.3,
                tone_weight=0.2,
                speaker="single"
            ))

        self.logger.info(f"文本解析完成，共 {len(segments)} 个段落")
        return segments

    def parse(self, script_text: str) -> List[ScriptSegment]:
        """
        主解析方法

        Args:
            script_text: 文案文本（JSON 格式或纯文本）

        Returns:
            List[ScriptSegment]: 文案段落列表
        """
        self.logger.info(f"开始解析文案，前100字符: {script_text[:100] if script_text else '空'}")

        if not script_text:
            return self._get_default_segments()

        try:
            return self.parse_json_script(script_text)
        except Exception as e:
            self.logger.error(f"文案解析异常: {e}")
            return self._get_default_segments()

    def _get_default_segments(self) -> List[ScriptSegment]:
        """获取默认文案段落"""
        return [
            ScriptSegment(
                segment_id="seg_000",
                text="欢迎观看",
                scene_type=SceneType.OPENING,
                emotion=EmotionType.CALM,
                tone="开场",
                emotion_weight=0.3,
                tone_weight=0.2,
                speaker="single"
            ),
            ScriptSegment(
                segment_id="seg_001",
                text="今天的内容就到这里",
                scene_type=SceneType.ENDING,
                emotion=EmotionType.CALM,
                tone="结束",
                emotion_weight=0.3,
                tone_weight=0.2,
                speaker="single"
            )
        ]

    def is_valid_script(self, script_text: str) -> tuple[bool, str]:
        """
        验证文案格式是否正确

        Args:
            script_text: 文案文本

        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        if not script_text:
            return False, "文案内容为空"

        try:
            # 使用保留键值对的方式解析
            parsed = _parse_json_script(script_text)

            if not isinstance(parsed, list):
                return False, "文案必须是 JSON 对象格式"

            required_keys = ["开场"]
            found_keys = set()
            for key, value in parsed:
                found_keys.add(key)
            
            for key in required_keys:
                if key not in found_keys:
                    return False, f"缺少必需字段: {key}"

            return True, ""

        except json.JSONDecodeError as e:
            return False, f"JSON 格式错误: {str(e)}"


def create_script_parser() -> ScriptParser:
    """
    创建文案解析器实例

    Returns:
        ScriptParser: 文案解析器实例
    """
    return ScriptParser()
