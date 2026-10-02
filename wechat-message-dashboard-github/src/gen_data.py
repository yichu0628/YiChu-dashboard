# -*- coding: utf-8 -*-
"""
微信看板数据层（可复用模块）

从微信 4.x 解密归档 SQLite 中提取并分析数据，输出结构化 JSON：
- 会话分类：work(工作与项目) / personal(个人聊天) / gzh(公众号/通知) / marketing(营销/推送)
- 待回复检测与分级（P0=被点名/24h 内对方未回，P1=长期未回）
- 24h 新增聊天
- 主线任务提取、项目节点/约定提取
- 公众号（biz_message 库）与营销号统计

依赖：仅 Python 标准库（sqlite3 / json / hashlib / re / time / os / argparse）。
"""
import sqlite3
import os
import hashlib
import time
import json
import re
import argparse

# ---------- 分类关键词（模块级常量） ----------
WORK_KW = r'老师|教练|客户|经理|主管|老板|客服|技术|工程|公司|科技|官方|项目|合作|商务|销售|设计|开发|制造|团队|3d|打印|拓竹|创想|模灵|中航|复材|艾科|泓研|科创|赛事|比赛|大赛|联赛|黑客松|院|班|团|委|学生会|社团|课|志愿|年级|军训|队|咨询|代理|经销|工作室|工厂|招聘|实习|就业|讲座|实验室|课题'
FAMILY_KW = r'妈|爸|爹|娘|姐|妹|哥|弟|姨|叔|舅|姑|姥|奶|爷|外婆|外公|奶奶|爷爷'
MARKETING_KW = r'下单|助手|客服|红包|券|秒杀|团购|优惠|门店|店长|福利|领取|推广|优惠券|会员|积分|签到|抽奖|代购|小店|商行|代理|团长|领券|外卖|打车|出行'

# 任务/节点关键词
TASK_KW = re.compile(r'帮我|麻烦|请你|需要你|记得|别忘了|尽快|抓紧|确认|安排|负责|交付|提交|完成|处理|跟进|回我|回复|有空|看一下|帮忙|今天|明天|后天|这周|下周|月底|截止|deadline|ddl|验收|评审|碰面|见面|会议|开会|项目|节点|里程碑|约定|说好|约好')
NODE_KW = re.compile(r'(今天|明天|后天|这周|下周|周末|周[一二三四五六日天]|下周[一二三四五六日天]|\d{1,2}月\d{1,2}[日号]|\d{1,2}[.:：]\d{2}|截止|deadline|ddl|月底|月初|这月|下月|验收|交付|提交|评审|会议|开会|碰面|见面|考试|比赛|答辩|汇报|节点|里程碑)')

# 服务/通知类会话（并入公众号/通知分类）
SERVICE_ACCOUNTS = ("notifymessage", "newsapp", "weixin", "filehelper", "medianote",
                    "fmessage", "qmessage", "tmessage", "floatbottle")


def extract_text(mc):
    """从 message_content 提取可读文本
    @param mc: str|bytes|None - message_content 原始字段
    @returns str - 清理后的文本
    """
    if mc is None:
        return ""
    if isinstance(mc, str):
        s = mc
    elif isinstance(mc, bytes):
        s = mc.decode('utf-8', 'ignore')
    else:
        s = str(mc)
    s = s.replace('\x00', '')
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]+', '', s)
    return s


def split_sender(s, is_group):
    """拆分群聊消息的发送者与正文
    @param s: str - 原始消息文本（群聊为 'sender:\\n内容'）
    @param is_group: bool - 是否群聊
    @returns (str, str) - (发送者, 正文)；私聊返回 ("", 原文)
    """
    if not is_group:
        return "", s
    m = re.match(r'^([A-Za-z0-9_\-@]{3,60}):\n', s)
    if m:
        return m.group(1), s[m.end():]
    return "", s


def is_group(un):
    """判断会话是否为群聊
    @param un: str - 会话 username
    @returns bool - 是否群聊
    """
    return un.endswith("@chatroom")


def categorize(un, name):
    """按 username 与昵称判定会话分类
    @param un: str - 会话 username
    @param name: str - 显示名（备注/昵称）
    @returns str - work / personal / gzh / marketing
    """
    if un.startswith("gh_"):
        return "gzh"
    if un.endswith("@openim") or "@kefu.openim" in un:
        return "marketing"
    if un in SERVICE_ACCOUNTS:
        return "gzh"  # 服务/通知并入公众号/通知
    if un.endswith("@chatroom"):
        # 群聊：按名称分 work / personal
        return "work" if re.search(WORK_KW, name) else "personal"
    # 私聊
    if re.search(MARKETING_KW, name):
        return "marketing"
    if re.search(FAMILY_KW, name):
        return "personal"
    if re.search(WORK_KW, name):
        return "work"
    return "personal"


def cut_sentence(txt):
    """截断长文本用于展示
    @param txt: str - 原文
    @returns str - 不超过 120 字的文本
    """
    txt = txt.strip()
    if len(txt) > 120:
        txt = txt[:120] + "…"
    return txt


def generate(db_dir, self_wxid, out_path, self_aliases=None):
    """主流程：解析归档数据并输出结构化 JSON
    @param db_dir: str - 微信归档目录（含 message_*.db / contact.db / biz_message_*.db）
    @param self_wxid: str - 本人 wxid（如 wxid_xxx）
    @param out_path: str - 输出 JSON 文件路径
    @param self_aliases: list[str]|None - 本人昵称别名（用于群聊 @我 检测）
    @returns dict - 生成的结构化数据
    """
    self_aliases = list(self_aliases or [])

    def conn(db):
        """以只读方式打开归档数据库
        @param db: str - 数据库文件名
        @returns sqlite3.Connection - 只读连接
        """
        return sqlite3.connect(f"file:{os.path.join(db_dir, db)}?mode=ro", uri=True)

    # ---------- 1. contact 映射 ----------
    c = conn("contact.db")
    cur = c.cursor()
    cur.execute("SELECT id, username, nick_name, remark, local_type FROM contact")
    contact = {}
    for i, u, nick, remark, lt in cur.fetchall():
        contact[u] = {"id": i, "nick": nick or "", "remark": remark or "", "type": lt}
    SELF_ID = contact.get(self_wxid, {}).get("id")
    SELF_NICK = contact.get(self_wxid, {}).get("remark") or contact.get(self_wxid, {}).get("nick") or self_wxid
    member_count = {}
    cur.execute("SELECT room_id, COUNT(*) FROM chatroom_member GROUP BY room_id")
    for rid, cnt in cur.fetchall():
        member_count[rid] = cnt
    c.close()

    def display_name(un):
        """获取会话显示名（备注优先于昵称）
        @param un: str - 会话 username
        @returns str - 显示名
        """
        info = contact.get(un, {})
        return info.get("remark") or info.get("nick") or un

    # 本人昵称别名（用于 @我 检测）
    SELF_ALIASES = set()
    for frag in [SELF_NICK] + self_aliases:
        if frag:
            SELF_ALIASES.add(frag)

    # ---------- 2. 收集普通会话（跨库合并） ----------
    locs = {}
    for db in ["message_0.db", "message_1.db", "message_2.db"]:
        try:
            m = conn(db)
        except Exception:
            continue
        cur = m.cursor()
        cur.execute("SELECT user_name FROM Name2Id")
        names = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")
        existing = set(r[0] for r in cur.fetchall())
        m.close()
        for un in names:
            if un == self_wxid:
                continue
            h = hashlib.md5(un.encode('utf-8')).hexdigest()
            tab = f"Msg_{h}"
            if tab in existing:
                locs.setdefault(un, []).append((db, tab))

    print(f"普通会话（去重后）: {len(locs)}")

    now = int(time.time())
    DAY = 86400
    MAXD = {"7": now - 7 * DAY, "30": now - 30 * DAY, "90": now - 90 * DAY}

    result = []
    mention_msgs = []   # 收集含 @ 的群聊消息用于点名判定
    task_hits = []      # 主线任务候选
    node_hits = []      # 节点候选

    for idx, (un, positions) in enumerate(locs.items()):
        grp = is_group(un)
        name = display_name(un)
        category = categorize(un, name)
        cnt = 0
        tmin = None
        tmax = 0
        m7 = m30 = m90 = 0
        recent_all = []  # (create_time, sender, txt, rsid)
        for db, tab in positions:
            m = sqlite3.connect(f"file:{os.path.join(db_dir, db)}?mode=ro", uri=True)
            cur = m.cursor()
            cur.execute(f'SELECT COUNT(*), MIN(create_time), MAX(create_time) FROM "{tab}"')
            cc, tmin2, tmax2 = cur.fetchone()
            cnt += cc or 0
            if tmin2 is not None and (tmin is None or tmin2 < tmin):
                tmin = tmin2
            tmax = max(tmax, tmax2 or 0)
            for k, v in MAXD.items():
                cur.execute(f'SELECT COUNT(*) FROM "{tab}" WHERE create_time >= {v}')
                rv = cur.fetchone()[0]
                if k == "7":
                    m7 += rv
                elif k == "30":
                    m30 += rv
                else:
                    m90 += rv
            # 最近文本（80 条，用于待回复/点名/任务/节点分析）
            cur.execute(f'SELECT message_content, create_time, real_sender_id FROM "{tab}" WHERE local_type=1 ORDER BY local_id DESC LIMIT 80')
            for mc, ct, rsid in cur.fetchall():
                s = extract_text(mc)
                sender, txt = split_sender(s, grp)
                txt = txt.strip()
                if txt:
                    recent_all.append((ct, sender, txt, rsid))
            m.close()

        recent_all.sort(key=lambda x: -x[0])
        last_text = ""
        recents = []
        # 判定最后一条是否我发的 + 待回复
        pending = False
        priority = 0          # 0=无 1=留意 2=最高
        pending_reason = ""
        mentioned = False

        # 私聊：用 real_sender_id 判定 mine；群聊：用 sender 判定
        last_mine = None
        for ct, sender, txt, rsid in recent_all:
            if not last_text:
                last_text = txt
            snippet = txt[:160].replace('\n', ' ')
            if grp:
                mine = (sender == self_wxid)
                who = SELF_NICK if mine else (display_name(sender) if sender else "")
            else:
                if rsid and SELF_ID and rsid == SELF_ID:
                    mine = True
                elif rsid and rsid != SELF_ID:
                    mine = False
                else:
                    mine = None
                who = "我" if mine is True else ("对方" if mine is False else "")
            if len(recents) < 5:
                recents.append({"t": ct, "c": snippet, "mine": mine, "who": who or ""})
            if last_mine is None and mine is not None:
                last_mine = mine

        # ---- 点名检测（群聊 @我）----
        if grp:
            for ct, sender, txt, rsid in recent_all:
                if sender == self_wxid or not txt:
                    continue
                for mm in re.finditer(r'@([\u4e00-\u9fa5A-Za-z0-9_\-·•]{1,20})', txt):
                    nick = mm.group(1)
                    if nick in ("所有人", "全体成员", "all"):
                        continue
                    if nick in SELF_ALIASES or any(a in nick for a in SELF_ALIASES if len(a) >= 3):
                        mentioned = True
                        break
                if mentioned:
                    break

        # ---- 待回复判定 ----
        # 仅工作/个人会话纳入待回复；营销/公众号不纳入
        if category in ("work", "personal") and last_mine is False:
            pending = True
            age = now - recent_all[0][0] if recent_all else 0
            if grp:
                if mentioned:
                    priority = 2
                    pending_reason = "群聊被@点名"
                else:
                    # 群聊对方最后发言不算强待回复，除非近期
                    if age < DAY:
                        priority = 1
                        pending_reason = "群聊近期有未读动态"
                    else:
                        pending = False
            else:
                # 私聊对方最后发言
                if mentioned:
                    priority = 2
                    pending_reason = "被点名"
                elif age < DAY:
                    priority = 2
                    pending_reason = "24h内对方来信未回"
                elif age < 7 * DAY:
                    priority = 1
                    pending_reason = "数日内未回"
                else:
                    priority = 1
                    pending_reason = "长期未回"

        # ---- 主线任务 / 节点 候选 ----
        for ct, sender, txt, rsid in recent_all:
            if TASK_KW.search(txt):
                task_hits.append({"name": name, "category": category, "t": ct, "text": txt})
            if NODE_KW.search(txt):
                node_hits.append({"name": name, "category": category, "t": ct, "text": txt})

        members = 2
        if grp and un in contact:
            members = member_count.get(contact[un]["id"], 0) or 2

        result.append({
            "id": idx + 1,
            "username": un, "name": name, "category": category,
            "isGroup": grp, "members": members,
            "msgs": cnt, "msgs7": m7, "msgs30": m30, "msgs90": m90,
            "lastTime": tmax, "lastText": last_text or "",
            "recent": recents,
            "pending": pending, "priority": priority, "pendingReason": pending_reason,
            "mentioned": mentioned, "lastMine": last_mine,
        })
        if (idx + 1) % 100 == 0:
            print(f"  已处理 {idx + 1}/{len(locs)}")

    result.sort(key=lambda x: -x["msgs"])

    # ---------- 3. 待回复列表（分级） ----------
    pending_list = [r for r in result if r["pending"]]
    pending_list.sort(key=lambda x: (-x["priority"], -x["lastTime"]))

    # 24h 新增聊天
    new24 = [r for r in result if r["lastTime"] >= now - DAY]
    new24.sort(key=lambda x: -x["lastTime"])

    # ---------- 4. 主线任务聚合 ----------
    task_map = {}
    for h in task_hits:
        if h["category"] not in ("work", "personal"):
            continue
        key = h["name"]
        if key not in task_map or h["t"] > task_map[key]["t"]:
            task_map[key] = h
    tasks = sorted(task_map.values(), key=lambda x: -x["t"])
    mainline = []
    for h in tasks[:15]:
        mainline.append({"name": h["name"], "t": h["t"], "text": cut_sentence(h["text"])})

    # ---------- 5. 项目节点/约定 ----------
    nodes = sorted(node_hits, key=lambda x: -x["t"])
    milestones = []
    seen = set()
    for h in nodes:
        if h["category"] not in ("work", "personal"):
            continue
        key = (h["name"], h["text"][:40])
        if key in seen:
            continue
        seen.add(key)
        milestones.append({"name": h["name"], "t": h["t"], "text": cut_sentence(h["text"])})
        if len(milestones) >= 20:
            break

    # ---------- 6. 公众号（biz_message 库） ----------
    gzh = []
    for db in ["biz_message_0.db", "biz_message_1.db"]:
        try:
            m = sqlite3.connect(f"file:{os.path.join(db_dir, db)}?mode=ro", uri=True)
            cur = m.cursor()
            cur.execute("SELECT user_name FROM Name2Id WHERE user_name LIKE 'gh_%' OR user_name IN ('newsapp','notifymessage')")
            names = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")
            existing = set(r[0] for r in cur.fetchall())
            for un in names:
                h = hashlib.md5(un.encode('utf-8')).hexdigest()
                tab = f"Msg_{h}"
                if tab not in existing:
                    continue
                cur.execute(f'SELECT COUNT(*), MIN(create_time), MAX(create_time) FROM "{tab}"')
                cc, t0, t1 = cur.fetchone()
                base = un.split('@')[0]
                info = contact.get(base, {})
                nm = info.get("remark") or info.get("nick") or un
                gzh.append({"name": nm, "username": un, "msgs": cc or 0, "firstTime": t0 or 0, "lastTime": t1 or 0})
            m.close()
        except Exception as e:
            print(f"公众号库 {db} 处理失败: {e}")

    # 去重（跨库同名）
    gzh_map = {}
    for g in gzh:
        k = g["username"]
        if k not in gzh_map or g["lastTime"] > gzh_map[k]["lastTime"]:
            gzh_map[k] = g
    gzh = list(gzh_map.values())
    gzh.sort(key=lambda x: -x["lastTime"])

    # 营销号（从 result 里筛）
    marketing = [r for r in result if r["category"] == "marketing"]
    marketing.sort(key=lambda x: -x["lastTime"])

    # ---------- 输出 ----------
    out = {
        "self": {"username": self_wxid, "nick": SELF_NICK, "id": SELF_ID},
        "generatedAt": time.strftime("%Y-%m-%d %H:%M"),
        "tmin": min((s["lastTime"] for s in result), default=0),
        "tmax": max((s["lastTime"] for s in result), default=0),
        "totalSessions": len(result),
        "totalMsgs": sum(s["msgs"] for s in result),
        "stats": {
            "pendingTotal": len(pending_list),
            "pendingP0": sum(1 for p in pending_list if p["priority"] == 2),
            "pendingP1": sum(1 for p in pending_list if p["priority"] == 1),
            "new24h": len(new24),
            "work": sum(1 for r in result if r["category"] == "work"),
            "personal": sum(1 for r in result if r["category"] == "personal"),
            "gzh": len(gzh),
            "marketing": len(marketing),
        },
        "pending": pending_list,
        "new24h": new24,
        "mainlineTasks": mainline,
        "milestones": milestones,
        "gzh": gzh,
        "marketing": marketing,
        "conversations": result,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"\n完成：{len(result)} 个会话，总消息 {out['totalMsgs']} 条")
    print(f"待回复 {len(pending_list)}（P0 {out['stats']['pendingP0']} / P1 {out['stats']['pendingP1']}）")
    print(f"24h新增 {len(new24)} · 主线任务 {len(mainline)} · 节点 {len(milestones)}")
    print(f"公众号 {len(gzh)} · 营销号 {len(marketing)}")
    print(f"分类: work {out['stats']['work']} / personal {out['stats']['personal']}")
    print(f"已输出 -> {out_path}")
    return out


def main():
    """命令行入口：解析参数并调用 generate
    """
    ap = argparse.ArgumentParser(description="生成微信看板结构化数据")
    ap.add_argument("--db-dir", required=True, help="微信归档目录")
    ap.add_argument("--self", required=True, help="本人 wxid")
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    ap.add_argument("--aliases", nargs="*", default=[], help="本人昵称别名（可选）")
    args = ap.parse_args()
    generate(args.db_dir, args.self, args.out, args.aliases)


if __name__ == "__main__":
    main()
