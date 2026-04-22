"""
情绪映射服务
加载 YAML 映射配置文件，提供按情绪标签查询情绪向量的能力
"""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("indextts-api.emotion")


class EmotionMappingService:
    """
    情绪标签 → 情绪向量（emo_vector）映射服务

    启动时从 YAML 文件加载映射表到内存，提供 O(1) 的标签查询能力。
    映射文件不存在或格式错误时不阻塞服务启动，通过 available / load_error 状态区分。

    状态说明：
    - 文件不存在: available=False, load_error=False → 客户端传 emotion 时返回 400
    - 文件格式错误: available=False, load_error=True → 客户端传 emotion 时返回 503
    - 加载成功: available=True, load_error=False → 正常查询

    查询结果：
    - resolve() 返回 (emo_vector, error) 元组
    - emo_vector: 8元素列表 [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm] 或 None
    - error: 错误信息或 None
    """

    VEC_KEYS = ["vec1", "vec2", "vec3", "vec4", "vec5", "vec6", "vec7", "vec8"]
    DEFAULT_INTENSITY = 1.0

    def __init__(self, mapping_file: str | Path) -> None:
        self._mapping_file = Path(mapping_file)
        self._mappings: dict[str, dict[str, float]] = {}
        self._available: bool = False
        self._load_error: bool = False

    def load(self) -> None:
        """
        加载并校验映射配置文件。

        文件不存在 → 日志 WARNING，available=False
        格式错误 → 日志 ERROR，load_error=True
        校验通过 → 日志 INFO，available=True
        """
        if not self._mapping_file.exists():
            logger.warning(f"情绪映射文件不存在: {self._mapping_file}，情绪控制功能不可用")
            self._mappings = {}
            self._available = False
            self._load_error = False
            return

        try:
            with open(self._mapping_file, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.error(f"情绪映射文件解析失败: {self._mapping_file}，错误: {e}")
            self._mappings = {}
            self._available = False
            self._load_error = True
            return

        if not isinstance(raw_data, dict):
            logger.error(f"情绪映射文件格式错误: {self._mapping_file}，顶层应为 key-value 结构")
            self._mappings = {}
            self._available = False
            self._load_error = True
            return

        mappings: dict[str, dict[str, float]] = {}
        skipped_count = 0

        for label, value in raw_data.items():
            if not isinstance(label, str):
                logger.warning(f"跳过非字符串标签: {label!r}")
                skipped_count += 1
                continue

            if not isinstance(value, dict):
                logger.warning(f"跳过标签 '{label}'：值应为字典格式")
                skipped_count += 1
                continue

            vec_dict = {}
            
            # 保存 vec1-vec8
            for key in self.VEC_KEYS:
                if key in value:
                    val = value[key]
                    if not isinstance(val, (int, float)):
                        logger.warning(f"跳过标签 '{label}'：{key} 应为数字")
                        vec_dict = {}
                        break
                    vec_dict[key] = float(val)
            
            # 保存 speed 字段（如果存在）
            if "speed" in value:
                speed_val = value["speed"]
                if isinstance(speed_val, (int, float)):
                    vec_dict["speed"] = float(speed_val)
                else:
                    logger.warning(f"跳过标签 '{label}' 的 speed 字段：应为数字")

            if vec_dict:
                mappings[label] = vec_dict

        self._mappings = mappings
        self._available = True
        self._load_error = False
        logger.info(f"情绪映射表加载成功，共 {len(mappings)} 个标签")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def load_error(self) -> bool:
        return self._load_error

    def resolve(self, emotion_label: str, intensity: float = None) -> tuple[list | None, float, str | None]:
        """
        查询情绪标签对应的 emo_vector 和 speed

        Args:
            emotion_label: 情绪标签（如"高兴"）
            intensity: 强度因子，会乘以向量中的每个值

        Returns:
            (emo_vector, speed, error) 元组
            - success: (8元素列表, speed值, None)
            - label not found: (None, 1.0, error_message)
            - service unavailable: (None, 1.0, error_message)
        """
        if not self._available:
            if self._load_error:
                return None, 1.0, "情绪映射表不可用（配置错误），请联系管理员"
            return None, 1.0, "情绪映射表未加载，请确认配置文件存在"

        if emotion_label not in self._mappings:
            available_labels = ", ".join(sorted(self._mappings.keys()))
            return None, 1.0, f"未知情绪标签 '{emotion_label}'，可用标签: {available_labels}"

        vec_dict = self._mappings[emotion_label]

        emo_vector = [0.0] * 8
        for key, val in vec_dict.items():
            if key != "speed":
                idx = self.VEC_KEYS.index(key)
                emo_vector[idx] = val

        speed = vec_dict.get("speed", 1.0)

        return emo_vector, speed, None

    def get_speed(self, emotion_label: str) -> float:
        """
        获取情绪标签对应的语速

        Args:
            emotion_label: 情绪标签（如"高兴"）

        Returns:
            语速值，未找到时返回默认值 1.0
        """
        if not self._available or emotion_label not in self._mappings:
            return 1.0

        vec_dict = self._mappings[emotion_label]
        return vec_dict.get("speed", 1.0)

    def get_available_labels(self) -> list[str]:
        """获取所有可用的情绪标签"""
        return sorted(self._mappings.keys())
