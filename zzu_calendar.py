#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
郑州大学学生处「通知公告」截止时间抓取 + 日历(.ics)生成器（云端版）
==================================================================
跑在 GitHub Actions 上，每天自动抓取并生成 calendar.ics，
由 GitHub Pages 托管，iPhone「订阅日历」后自动更新。

用法：
    python3 zzu_calendar.py scrape   抓取列表页+详情，提取截止时间 -> deadlines.json
    python3 zzu_calendar.py ics      读取 deadlines.json -> calendar.ics（提前1天提醒）
    python3 zzu_calendar.py all      = scrape + ics

说明：
    * deadlines.json 是「提取结果」，可人工复核后再生成日历。
    * 事件 UID 由「名称+截止时间」哈希生成，跨天保持稳定，订阅端据此判重、不重复。
    * 提醒为每个截止时间「提前 1 天」（VALARM TRIGGER:-P1D）。
"""

import re
import json
import os
import html
import hashlib
import urllib.request
from datetime import datetime, date, timedelta, timezone

BASE = "https://www5.zzu.edu.cn/student/"
LIST_URL = BASE + "tzgg.htm"
PAGES = 2            # 抓取最新几页（每页约 10 条；翻页编号自 389 递减）
OUT_JSON = "deadlines.json"
OUT_ICS = "calendar.ics"
REMIND_HOURS = 24    # 提前 1 天

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# --------------------------------------------------------------------------
# 抓取
# --------------------------------------------------------------------------

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    head = data[:2000].decode("utf-8", "ignore")
    m = re.search(r'charset=["\']?([\w-]+)', head)
    enc = m.group(1) if m else "utf-8"
    try:
        return data.decode(enc, "ignore")
    except Exception:
        return data.decode("utf-8", "ignore")


def strip_tags(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    return s


def parse_list_page(page_html: str):
    """返回 [(title, date_str, href), ...]"""
    items = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        href, inner = m.group(1), m.group(2)
        href = href.replace("../", "")  # 第2页起链接带 ../ 前缀
        if not (href.startswith("info/1003/") or href.startswith("content.jsp")):
            continue
        t = re.search(r"<span>(.*?)</span>", inner, re.S)
        title = strip_tags(t.group(1)) if t else strip_tags(inner)
        d = re.search(r"<em>(.*?)</em>", inner, re.S)
        date_str = strip_tags(d.group(1)) if d else ""
        if title:
            items.append((title, date_str, href))
    return items


def list_url_for_page(page: int) -> str:
    """第1页=tzgg.htm（最新），第2页=tzgg/389.htm，以此递减。"""
    if page <= 1:
        return LIST_URL
    return BASE + f"tzgg/{391 - page}.htm"


# --------------------------------------------------------------------------
# 截止时间提取（启发式，结果写入 deadlines.json）
# --------------------------------------------------------------------------

DEADLINE_KW = ["截止", "前将", "前完成", "前发送", "前提交", "前报送", "前加入",
               "前报", "日前", "前交", "前寄", "公示期"]
TIME_RE = r"(上午|中午|下午|晚上)?\s*(\d{1,2})[:：](\d{2})"


def _year_of(pub_date_str: str) -> int:
    m = re.search(r"(\d{4})年", pub_date_str)
    return int(m.group(1)) if m else datetime.now().year


def extract_events(title: str, pub_date: str, url: str, text: str):
    """从通知正文里抽取候选截止时间。返回 event dict 列表。"""
    # 原文常有排版空格把日期拆开（如 "10月1 5 日"），先规范化
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    text = re.sub(r"\s*月\s*", "月", text)
    text = re.sub(r"\s*日\s*", "日", text)
    year = _year_of(pub_date)
    events = []
    seen = set()
    for clause in re.split(r"[。；;\n]", text):
        if not any(k in clause for k in DEADLINE_KW):
            continue
        # 该分句内的所有日期
        for dm in re.finditer(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日", clause):
            y = int(dm.group(1)) if dm.group(1) else year
            mo, d = int(dm.group(2)), int(dm.group(3))
            if not (1 <= mo <= 12 and 1 <= d <= 31):
                continue
            tail = clause[dm.end():dm.end() + 24]
            tm = re.search(TIME_RE, tail)
            hour = minute = None
            if tm:
                hour = int(tm.group(2)); minute = int(tm.group(3))
                part = tm.group(1)
                if part == "下午" and hour < 12:
                    hour += 12
                if part == "中午" and hour < 11:
                    hour += 12
                if part == "上午" and hour == 12:
                    hour = 0
                if hour == 24:  # 24:00 -> 当日 23:59
                    hour, minute = 23, 59
                hour = min(hour, 23)
            key = (y, mo, d, hour, minute)
            if key in seen:
                continue
            seen.add(key)
            when = f"{y:04d}-{mo:02d}-{d:02d}"
            if hour is not None:
                when += f"T{hour:02d}:{minute:02d}:00"
            events.append({
                "name": title,
                "deadline": when,
                "notice": title,
                "url": url,
                "kind": "截止" if ("截止" in clause) else "节点",
                "note": clause.strip(),
                "publish": pub_date,
            })
    return events


def _today():
    """北京时间今天（GitHub Actions 跑在 UTC，须按国内时区判断日期）。"""
    return datetime.now(timezone(timedelta(hours=8))).date()


def _is_future(when: str) -> bool:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", when or "")
    return bool(m) and date(int(m.group(1)), int(m.group(2)), int(m.group(3))) >= _today()


def scrape():
    # 载入上次结果：详情页抓取被拒/失败时，沿用该通知上次抓到的未过期节点
    prev_by_notice = {}
    if os.path.exists(OUT_JSON):
        try:
            with open(OUT_JSON, encoding="utf-8") as f:
                for e in json.load(f).get("events", []):
                    prev_by_notice.setdefault(e.get("notice", ""), []).append(e)
        except Exception:
            pass

    all_items = []
    for p in range(1, PAGES + 1):
        try:
            html = fetch(list_url_for_page(p))
            items = parse_list_page(html)
            print(f"第 {p} 页：解析到 {len(items)} 条通知")
            all_items.extend(items)
        except Exception as e:
            print(f"第 {p} 页抓取失败：{e}")

    events = []
    for title, pub_date, href in all_items:
        full = href if href.startswith("http") else BASE + href
        denied = False
        txt = ""
        try:
            raw = fetch(full)
            if "没有访问" in strip_tags(raw[:4000]):
                # content.jsp 动态页对境外 IP 返回“您没有访问当前栏目的权限”
                denied = True
            else:
                txt = strip_tags(raw)
        except Exception as e:
            print(f"详情抓取失败 {title}: {e}")
            denied = True
        ev = [] if denied else extract_events(title, pub_date, full, txt)
        if denied:
            ev = [e for e in prev_by_notice.get(title, []) if _is_future(e.get("deadline"))]
            if ev:
                events.extend(ev)
                print(f"  {title}  ->  {len(ev)} 个节点（沿用上次结果）")
                continue
        if ev:
            events.extend(ev)
        print(f"  {title}  ->  {len(ev)} 个节点")

    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": LIST_URL,
        "events": events,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {OUT_JSON}（共 {len(events)} 个节点）")


# --------------------------------------------------------------------------
# .ics 生成
# --------------------------------------------------------------------------

def _fold(line: str) -> str:
    """按 RFC5545 以 75 个八位字节折行，续行以空格开头。"""
    out = []
    cur = ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 74:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def _ics_dt(when: str):
    """'YYYY-MM-DD' -> 全日期; 'YYYY-MM-DDTHH:MM:SS' -> 本地时间（时长30分钟）。"""
    if "T" in when:
        dt = datetime.strptime(when, "%Y-%m-%dT%H:%M:%S")
        end = dt + timedelta(minutes=30)
        return (f"DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}\r\n"
                f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}")
    return f"DTSTART;VALUE=DATE:{when.replace('-', '')}"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def generate_ics(json_path=OUT_JSON, out_path=OUT_ICS, today=None):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    today = today or _today()
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ZZU通知截止提醒//CN//ZH",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]

    n = 0
    for ev in data["events"]:
        when = ev.get("deadline", "")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", when)
        if not m:
            continue
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d < today:      # 只保留今天及以后
            continue
        summary = ev.get("name", "通知")
        # 稳定 UID：由「名称+截止时间」哈希，订阅端据此判重，避免重复
        h = hashlib.sha1(f"{summary}|{when}".encode("utf-8")).hexdigest()[:16]
        uid = f"zzu-{h}@zzu.edu.cn"
        note = ev.get("note", "")
        url = ev.get("url", "")
        desc = f"{summary}\n截止时间：{when}\n来源：{note}\n原文：{url}"
        lines += ["BEGIN:VEVENT", f"UID:{uid}",
                  f"DTSTAMP:{now_utc}", _ics_dt(when),
                  f"SUMMARY:{_fold(_escape(summary))}",
                  f"DESCRIPTION:{_fold(_escape(desc))}"]
        # 提前一天提醒
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY",
                  f"DESCRIPTION:{_fold(_escape('截止提醒：' + summary))}",
                  f"TRIGGER:-PT{REMIND_HOURS}H", "END:VALARM",
                  "END:VEVENT"]
        n += 1

    lines += ["END:VCALENDAR"]
    content = "\r\n".join(lines) + "\r\n"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"已生成 {out_path}（{n} 个未来事件，每个提前 {REMIND_HOURS} 小时提醒）")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "scrape":
        scrape()
    elif cmd == "ics":
        generate_ics()
    elif cmd == "all":
        scrape()
        generate_ics()
    else:
        print(__doc__)
