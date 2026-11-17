"""Incident report rendering (Markdown + printable HTML → browser 'Save as PDF')."""
from __future__ import annotations

import html

from .engine import LEVEL_KO

DECISION_KO = {
    "confirmed_device": "기기 확인함", "false_positive": "오탐", "needs_more_check": "추가 확인", "no_action": "조치 없음",
}
LIMITS_KO = [
    "페어링·연결된 기기는 광고를 멈추므로 BLE 광고 기반 단서로 보이지 않을 수 있습니다.",
    "전원이 꺼진 기기, LTE/5G만 쓰는 기기, 유선·자기유도 장치는 이 구성으로 감지할 수 없습니다.",
    "신호 강도(RSSI)로 좌석이나 사람을 특정할 수 없습니다. 복도·옆 교실 신호가 섞일 수 있습니다.",
    "시그니처는 누구나 흉내 낼 수 있으며, 같은 회사의 다른 기기에서 오탐이 날 수 있습니다.",
    "v0.1은 시뮬레이터·리플레이로만 검증되었고 실제 시험장 현장 검증 전입니다.",
]


def _hhmmss(ts: str) -> str:
    return ts[11:19] if ts and len(ts) >= 19 else ts


def render_markdown(d: dict) -> str:
    m, st = d["manifest"], d["status"]
    meta = m.get("meta", {})
    L = [f"# 시험장 RF 단서 기록 보고서 (초안)", "", f"> {d['disclaimer']}", ""]
    L += ["## 1. 시험 정보", "",
          f"| 항목 | 내용 |", "| --- | --- |",
          f"| 시험 | {meta.get('exam', '-')} |", f"| 교시 | {meta.get('period', '-')} |",
          f"| 시험장/고사실 | {meta.get('site', '-')} / {meta.get('room', '-')} |",
          f"| 세션 ID | {m['session_id']} |", f"| 시작 | {m['started_at']} |", f"| 종료 | {m.get('closed_at', '-')} |",
          f"| 허브 버전 | {m['hub_version']} |", ""]
    L += ["## 2. 장비 구성", "", "| 센서 ID | 드라이버 | 하드웨어 | 송신 가능 |", "| --- | --- | --- | --- |"]
    for sid, s in (m.get("sensors") or {}).items():
        L.append(f"| {sid} | {s.get('driver') or '-'} | {s.get('hw') or '-'} | {s.get('tx_capable', '-')} |")
    b = d["baseline"]
    L += ["", "## 3. 빈 교실 기준선", "", f"기준선 신호 묶음 {b['groups']}개: " +
          ", ".join(f"{k} {v}" for k, v in sorted(b["by_kind"].items())) if b["groups"] else "기준선 없음", ""]
    L += ["## 4. 시험 중 단서 타임라인", "",
          "| 단서 | 등급 | 처음 | 마지막 | 내용 | 최고 신호 | 감독관 판단 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for c in d["clues"]:
        dec = c["decisions"][-1]["decision"] if c["decisions"] else ""
        rssi = f"{c['max_rssi']:.0f} dBm" if c["max_rssi"] is not None else "-"
        L.append(f"| {c['clue_id']} | {LEVEL_KO[c['level']]} | {_hhmmss(c['ts_first'])} | {_hhmmss(c['ts_last'])} | "
                 f"{c['title']} | {rssi} | {DECISION_KO.get(dec, '미기록')} |")
    if not d["clues"]:
        L.append("| - | - | - | - | 단서 없음 | - | - |")
    L += ["", "## 5. 단서별 근거와 조치", ""]
    for c in d["clues"]:
        L += [f"### {c['clue_id']} — {c['title']} ({LEVEL_KO[c['level']]})", ""]
        L += [f"- 근거: " + "; ".join(c["reasons"])]
        if c["signature_ids"]:
            L.append(f"- 일치한 시그니처: {', '.join(c['signature_ids'])}")
        L.append(f"- 관측 {c['count']}회, 서로 다른 가명 기기 {c['distinct_subjects']}개, 센서 {', '.join(c['sensors'])}")
        for a in c["decisions"]:
            chk = f" / 확인: {', '.join(a.get('checklist', []))}" if a.get("checklist") else ""
            L.append(f"- {_hhmmss(a['ts'])} {a.get('actor_role', '')}: {DECISION_KO[a['decision']]}"
                     f"{chk}{(' — ' + a['note']) if a.get('note') else ''}")
        L.append("")
    L += ["## 6. 이 구성의 탐지 한계", ""] + [f"- {x}" for x in LIMITS_KO]
    L += ["", "## 7. 무결성 정보", "",
          f"- 증거 원장 마지막 해시: `{d['ledger_head']}`",
          f"- 세션 키 지문(키 자체 아님, 세션 종료 시 키 폐기): `{m['session_key_fingerprint']}`",
          "- 검증: `exam-uncheat verify <세션 폴더>` (해시 체인 + SHA256SUMS)",
          f"- 보존: {m['retention_days']}일 후 자동 삭제 예정 ({m['delete_after'][:10]})", ""]
    return "\n".join(L)


def render_html(d: dict) -> str:
    md = render_markdown(d)
    body = []
    in_table = False
    for line in md.splitlines():
        esc = html.escape(line)
        if line.startswith("| "):
            cells = [html.escape(c.strip()) for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("- "):
                continue
            if not in_table:
                body.append("<table>")
                in_table = True
                body.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
            else:
                body.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            body.append("</table>")
            in_table = False
        if line.startswith("### "):
            body.append(f"<h3>{esc[4:]}</h3>")
        elif line.startswith("## "):
            body.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("# "):
            body.append(f"<h1>{esc[2:]}</h1>")
        elif line.startswith("> "):
            body.append(f"<p class='disc'>{esc[5:]}</p>")
        elif line.startswith("- "):
            body.append(f"<li>{esc[2:]}</li>")
        elif line.strip():
            body.append(f"<p>{esc}</p>")
    if in_table:
        body.append("</table>")
    css = ("body{font-family:system-ui,'Noto Sans KR',sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#111}"
           "table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border:1px solid #bbb;padding:4px 6px;font-size:13px}"
           "th{background:#f2f2f2}.disc{background:#fff4e5;border-left:4px solid #e69500;padding:8px}"
           "@media print{button{display:none}}")
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>RF 단서 기록 보고서</title>"
            f"<style>{css}</style></head><body><button onclick='window.print()'>인쇄 / PDF로 저장</button>"
            + "\n".join(body) + "</body></html>")
