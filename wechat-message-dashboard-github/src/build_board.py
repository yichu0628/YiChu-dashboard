# -*- coding: utf-8 -*-
"""
看板构建层（可复用模块）

从 conversations.json 精简数据并注入看板模板，生成最终自包含 HTML。
- 精简 recent / lastText，保留微信 username/wxid 原始标识
- 透传新字段：category / pending / priority / mentioned / lastMine
- 透传扩展列表：pending / new24h / mainlineTasks / milestones / gzh / marketing / stats
"""
import json
import argparse


def cut(s, n):
    """按长度截断字符串
    @param s: str|None - 原始字符串
    @param n: int - 最大长度
    @returns str - 截断后的字符串
    """
    if s is None:
        return ""
    s = str(s)
    return s if len(s) <= n else s[:n]


def slim_conv(c):
    """精简单个会话对象，保留微信 username/wxid
    @param c: dict - 原始会话对象
    @returns dict - 精简后的会话对象
    """
    return {
        "id": c.get("id"),
        "username": c.get("username", ""),
        "name": c.get("name", ""),
        "category": c.get("category", "personal"),
        "isGroup": bool(c.get("isGroup")),
        "members": c.get("members", 0),
        "msgs": c.get("msgs", 0),
        "msgs7": c.get("msgs7", 0),
        "msgs30": c.get("msgs30", 0),
        "msgs90": c.get("msgs90", 0),
        "lastTime": c.get("lastTime", 0),
        "lastText": cut(c.get("lastText"), 100),
        "recent": [
            {"t": r["t"], "c": cut(r.get("c"), 100), "mine": r.get("mine"), "who": r.get("who", "")}
            for r in (c.get("recent") or [])[:3]
        ],
        "pending": bool(c.get("pending")),
        "priority": c.get("priority", 0),
        "pendingReason": c.get("pendingReason", ""),
        "mentioned": bool(c.get("mentioned")),
        "lastMine": c.get("lastMine"),
    }


def build(src_json, tpl_path, out_html):
    """读取数据 JSON，注入模板，生成自包含 HTML
    @param src_json: str - conversations.json 路径
    @param tpl_path: str - 模板 HTML 路径（需含 __JSON__ 占位符）
    @param out_html: str - 最终 HTML 输出路径
    @returns str - 生成的 HTML 内容
    """
    with open(src_json, encoding="utf-8") as f:
        data = json.load(f)

    conv = [slim_conv(c) for c in data.get("conversations", [])]

    out = {
        "self": data.get("self", {}),
        "generatedAt": data.get("generatedAt", ""),
        "tmin": data.get("tmin", 0),
        "tmax": data.get("tmax", 0),
        "totalMsgs": data.get("totalMsgs", 0),
        "totalSessions": data.get("totalSessions", len(conv)),
        "stats": data.get("stats", {}),
        "pending": [slim_conv(c) for c in data.get("pending", [])],
        "new24h": [slim_conv(c) for c in data.get("new24h", [])],
        "mainlineTasks": [
            {"name": t.get("name", ""), "t": t.get("t", 0), "text": cut(t.get("text"), 120)}
            for t in data.get("mainlineTasks", [])
        ],
        "milestones": [
            {"name": m.get("name", ""), "t": m.get("t", 0), "text": cut(m.get("text"), 120)}
            for m in data.get("milestones", [])
        ],
        "gzh": [
            {"name": g.get("name", ""), "username": g.get("username", ""), "msgs": g.get("msgs", 0),
             "firstTime": g.get("firstTime", 0), "lastTime": g.get("lastTime", 0)}
            for g in data.get("gzh", [])
        ],
        "marketing": [slim_conv(c) for c in data.get("marketing", [])],
        "conversations": conv,
    }

    js = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    with open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()
    assert "__JSON__" in tpl, "模板缺少 __JSON__ 占位符"
    html = tpl.replace("__JSON__", js)

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"会话数: {len(conv)}")
    print(f"待回复: {len(out['pending'])} | 24h新增: {len(out['new24h'])} "
          f"| 主线任务: {len(out['mainlineTasks'])} | 节点: {len(out['milestones'])} "
          f"| 公众号: {len(out['gzh'])} | 营销: {len(out['marketing'])}")
    print(f"JSON 体积: {len(js) / 1024 / 1024:.2f} MB")
    print(f"HTML 体积: {len(html) / 1024 / 1024:.2f} MB")
    print(f"已输出 -> {out_html}")
    return html


def main():
    """命令行入口：解析参数并调用 build
    """
    ap = argparse.ArgumentParser(description="构建微信消息看板 HTML")
    ap.add_argument("--src", required=True, help="conversations.json 路径")
    ap.add_argument("--tpl", required=True, help="模板 HTML 路径")
    ap.add_argument("--out", required=True, help="最终 HTML 输出路径")
    args = ap.parse_args()
    build(args.src, args.tpl, args.out)


if __name__ == "__main__":
    main()
