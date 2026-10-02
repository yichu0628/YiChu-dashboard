# -*- coding: utf-8 -*-
"""
build_board 构建层自测：用最小数据夹具验证 HTML 注入与数据精简逻辑。
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)

from build_board import build, slim_conv   # noqa: E402


class TestBuildBoard(unittest.TestCase):
    """构建层单元测试"""

    def setUp(self):
        """准备临时夹具数据与输出路径
        """
        self.tmp = tempfile.mkdtemp()
        self.tpl = os.path.join(SRC, "board_template.html")
        fixture = {
            "self": {"username": "wxid_self", "nick": "我"},
            "generatedAt": "2026-09-13 12:00",
            "tmin": 100, "tmax": 200,
            "totalMsgs": 3, "totalSessions": 1,
            "stats": {"pendingTotal": 1, "pendingP0": 1, "pendingP1": 0},
            "pending": [], "new24h": [], "mainlineTasks": [],
            "milestones": [], "gzh": [], "marketing": [],
            "conversations": [
                {
                    "id": 1, "name": "测试会话", "category": "work",
                    "isGroup": False, "members": 2,
                    "msgs": 3, "msgs7": 3, "msgs30": 3, "msgs90": 3,
                    "lastTime": 200, "lastText": "你好",
                    "recent": [{"t": 200, "c": "你好", "mine": False, "who": "对方"}],
                    "pending": True, "priority": 2,
                    "pendingReason": "被点名", "mentioned": True, "lastMine": False,
                }
            ],
        }
        self.src = os.path.join(self.tmp, "conversations.json")
        with open(self.src, "w", encoding="utf-8") as f:
            json.dump(fixture, f, ensure_ascii=False)
        self.out = os.path.join(self.tmp, "board.html")

    def test_build_injects_json(self):
        """验证：输出 HTML 不含 __JSON__ 占位符，且注入关键数据
        """
        html = build(self.src, self.tpl, self.out)
        self.assertNotIn("__JSON__", html)
        self.assertIn("测试会话", html)
        self.assertTrue(os.path.exists(self.out))

    def test_slim_conv_preserves_username(self):
        """验证：本地版保留 username 原始字段
        """
        c = {"username": "wxid_secret", "name": "小明", "category": "personal"}
        slim = slim_conv(c)
        self.assertEqual(slim["username"], "wxid_secret")
        self.assertEqual(slim["name"], "小明")


if __name__ == "__main__":
    unittest.main()
