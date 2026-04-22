"""
测试文案解析器对重复标签的处理

验证修复：当文案中有重复的标签时，所有分段都应该被正确解析，而不是被覆盖
"""

import pytest
from business.llm.script_parser import ScriptParser, _parse_json_script


class TestDuplicateLabels:
    """测试重复标签处理"""

    def test_parse_json_preserves_duplicate_keys(self):
        """_parse_json_script 应该保留所有重复键"""
        script = '{"开心": "内容1", "开心": "内容2", "开心": "内容3"}'
        
        result = _parse_json_script(script)
        
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == ("开心", "内容1")
        assert result[1] == ("开心", "内容2")
        assert result[2] == ("开心", "内容3")

    def test_single_script_with_duplicate_labels(self):
        """单人文案有重复标签时，所有分段都应该被解析"""
        script = '''
        {
            "开场": "欢迎观看",
            "开心": "第一个开心的内容",
            "开心": "第二个开心的内容",
            "开心": "第三个开心的内容",
            "结束": "感谢观看"
        }
        '''
        
        parser = ScriptParser()
        segments = parser.parse(script)
        
        # 应该有 5 个分段，不是 3 个
        assert len(segments) == 5
        assert segments[0].tone == "开场"
        assert segments[1].tone == "开心"
        assert segments[1].text == "第一个开心的内容"
        assert segments[2].tone == "开心"
        assert segments[2].text == "第二个开心的内容"
        assert segments[3].tone == "开心"
        assert segments[3].text == "第三个开心的内容"
        assert segments[4].tone == "结束"

    def test_twenty_segments_with_five_duplicate_labels(self):
        """
        用户实际场景：20 个分段，5 种标签各有 3 个重复
        
        修复前：只解析出 10 个分段（重复标签被覆盖）
        修复后：正确解析出 20 个分段
        """
        script = '''
        {
            "开场": "欢迎观看今天的节目",
            "开心": "第一个开心的内容",
            "产品展示": "产品介绍第一部分",
            "开心": "第二个开心的内容",
            "开心": "第三个开心的内容",
            "产品展示": "产品介绍第二部分",
            "难过": "第一个难过的内容",
            "产品展示": "产品介绍第三部分",
            "难过": "第二个难过的内容",
            "难过": "第三个难过的内容",
            "生气": "第一个生气的内容",
            "功能介绍": "功能介绍第一部分",
            "生气": "第二个生气的内容",
            "生气": "第三个生气的内容",
            "功能介绍": "功能介绍第二部分",
            "低落": "第一个低落的内容",
            "功能介绍": "功能介绍第三部分",
            "低落": "第二个低落的内容",
            "低落": "第三个低落的内容",
            "结束": "感谢观看"
        }
        '''
        
        parser = ScriptParser()
        segments = parser.parse(script)
        
        # 验证：所有 20 个分段都被正确解析
        assert len(segments) == 20, f"期望 20 个分段，实际 {len(segments)} 个"
        
        # 验证：标签统计正确
        label_counts = {}
        for seg in segments:
            label_counts[seg.tone] = label_counts.get(seg.tone, 0) + 1
        
        assert label_counts["开场"] == 1
        assert label_counts["开心"] == 3
        assert label_counts["产品展示"] == 3
        assert label_counts["难过"] == 3
        assert label_counts["生气"] == 3
        assert label_counts["功能介绍"] == 3
        assert label_counts["低落"] == 3
        assert label_counts["结束"] == 1

    def test_no_duplicate_labels_unchanged(self):
        """没有重复标签时，行为应该与之前一致"""
        script = '''
        {
            "开场": "欢迎观看",
            "开心": "今天很开心",
            "产品展示": "这是产品",
            "结束": "感谢观看"
        }
        '''
        
        parser = ScriptParser()
        segments = parser.parse(script)
        
        assert len(segments) == 4
        assert segments[0].tone == "开场"
        assert segments[1].tone == "开心"
        assert segments[2].tone == "产品展示"
        assert segments[3].tone == "结束"

    def test_double_script_with_duplicate_labels(self):
        """双人文案有重复标签时，所有分段都应该被解析"""
        script = '''
        {
            "开场": [
                {"左边说话人": "大家好"},
                {"右边说话人": "欢迎观看"}
            ],
            "开心": [
                {"左边说话人": "今天很开心"},
                {"右边说话人": "是啊很开心"}
            ],
            "开心": [
                {"左边说话人": "第二段开心"},
                {"右边说话人": "第二段开心右"}
            ],
            "结束": [
                {"左边说话人": "感谢观看"},
                {"右边说话人": "下次再见"}
            ]
        }
        '''
        
        parser = ScriptParser()
        segments = parser.parse(script)
        
        # 开场 2 个 + 开心 2 个 + 开心 2 个 + 结束 2 个 = 8 个
        assert len(segments) == 8
        
        # 验证标签分布
        label_counts = {}
        for seg in segments:
            label_counts[seg.tone] = label_counts.get(seg.tone, 0) + 1
        
        assert label_counts["开场"] == 2
        assert label_counts["开心"] == 4  # 两段开心，每段左右各一个 = 2+2=4
        assert label_counts["结束"] == 2
