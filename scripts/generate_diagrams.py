#!/usr/bin/env python3
"""Generate publication-style draw.io (.drawio) diagrams and matching true-text SVG files.

Visual design follows restrained IEEE / ACM / USENIX Security academic conventions:
  - Neutral monochrome base (#FFFFFF / #F8F9FA, charcoal stroke #2B2D42) for standard components
  - Single muted academic slate-blue (#EEF3F8 / #2C5282) for core defense / proposed mechanisms
  - Single muted crimson (#FDF2F2 / #9B2C2C) for threat / rejection / isolation boundaries
  - No baked-in slide titles or rainbow legends; crisp typography, compact spacing, true SVG text.

Usage:
    python scripts/generate_diagrams.py
"""
from __future__ import annotations

import html
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "diagrams"

FONT_FAMILY = "Microsoft YaHei, PingFang SC, Helvetica Neue, Arial, sans-serif"

# Restrained 3-tone academic paper palette (Neutral + Slate Blue + Muted Crimson)
PALETTE = {
    "neutral": ("#FFFFFF", "#343A40", "#1A202C"),
    "subtle": ("#F8F9FA", "#6C757D", "#2D3748"),
    "container": ("#FAFAFB", "#ADB5BD", "#495057"),
    "accent": ("#EEF3F8", "#2C5282", "#1A365D"),
    "decision": ("#FFFFFF", "#2C5282", "#1A365D"),
    "alert": ("#FDF2F2", "#9B2C2C", "#742A2A"),
    "boundary": ("#FFFDFD", "#9B2C2C", "#9B2C2C"),
    "note": ("none", "none", "#495057"),
}


@dataclass
class Box:
    id: str
    x: int
    y: int
    w: int
    h: int
    label: str
    theme: str = "neutral"
    shape: str = "roundrect"  # roundrect | diamond | container | cylinder | note
    stroke_width: float = 1.2
    dashed: bool = False
    font_size: int = 11
    bold_first: bool = True
    align: str = "center"  # center | left


@dataclass
class Edge:
    id: str
    src: str
    dst: str
    label: str = ""
    color: str = "#343A40"
    dashed: bool = False
    stroke_width: float = 1.2
    src_anchor: str = "auto"  # top | bottom | left | right | auto
    dst_anchor: str = "auto"
    waypoints: list[tuple[int, int]] = field(default_factory=list)
    label_offset: tuple[int, int] = (0, -7)
    label_seg: int | None = None


@dataclass
class DiagramSpec:
    slug: str
    name: str
    width: int
    height: int
    boxes: list[Box]
    edges: list[Edge]
    footnote: str = ""


def _anchor_point(box: Box, side: str) -> tuple[float, float]:
    if side == "top":
        return (box.x + box.w / 2, box.y)
    if side == "bottom":
        return (box.x + box.w / 2, box.y + box.h)
    if side == "left":
        return (box.x, box.y + box.h / 2)
    if side == "right":
        return (box.x + box.w, box.y + box.h / 2)
    return (box.x + box.w / 2, box.y + box.h / 2)


def _auto_anchors(src: Box, dst: Box) -> tuple[str, str]:
    sx, sy = src.x + src.w / 2, src.y + src.h / 2
    dx, dy = dst.x + dst.w / 2, dst.y + dst.h / 2
    if abs(dx - sx) >= abs(dy - sy):
        return ("right", "left") if dx >= sx else ("left", "right")
    return ("bottom", "top") if dy >= sy else ("top", "bottom")


def _drawio_anchor_style(side: str, prefix: str) -> str:
    mapping = {"top": (0.5, 0.0), "bottom": (0.5, 1.0), "left": (0.0, 0.5), "right": (1.0, 0.5)}
    x, y = mapping[side]
    return f"{prefix}X={x};{prefix}Y={y};{prefix}Dx=0;{prefix}Dy=0;"


def _box_drawio_style(box: Box) -> str:
    fill, stroke, font_color = PALETTE[box.theme]
    parts = [
        f"fillColor={fill}",
        f"strokeColor={stroke}",
        f"fontColor={font_color}",
        f"strokeWidth={box.stroke_width}",
        f"fontSize={box.font_size}",
        f"fontFamily={FONT_FAMILY}",
        "whiteSpace=wrap",
        "html=1",
    ]
    if box.dashed:
        parts.extend(["dashed=1", "dashPattern=5 3"])

    if box.shape == "diamond":
        parts.insert(0, "rhombus")
    elif box.shape == "cylinder":
        parts.insert(0, "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=8")
    elif box.shape == "container":
        parts.insert(0, "rounded=1;arcSize=4")
        parts.extend(["verticalAlign=top", "align=left", "spacingTop=5", "spacingLeft=9", "fontStyle=1"])
    elif box.shape == "note":
        parts.insert(0, "rounded=0")
        parts.extend(["strokeColor=none", "fillColor=none", "align=left"])
    else:
        parts.insert(0, "rounded=1;arcSize=6")
        if box.align == "left":
            parts.extend(["align=left", "spacingLeft=9", "spacingRight=6"])
    return ";".join(parts) + ";"


def _format_drawio_label(box: Box) -> str:
    lines = box.label.split("\n")
    formatted = []
    for idx, line in enumerate(lines):
        esc = html.escape(line)
        if box.shape == "container":
            formatted.append(esc)
        elif idx == 0 and box.bold_first and len(lines) > 1:
            formatted.append(f"<b>{esc}</b>")
        elif idx > 0:
            formatted.append(f'<font style="font-size:{max(9.5, box.font_size - 1):.1f}px" color="#4A5568">{esc}</font>')
        else:
            formatted.append(f"<b>{esc}</b>" if box.bold_first else esc)
    return "<br>".join(formatted)


def build_drawio_xml(spec: DiagramSpec) -> str:
    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "agent": "rag-trust-demo", "version": "24.7.17"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": spec.slug, "name": spec.name})
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1100",
            "dy": "650",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": str(spec.width),
            "pageHeight": str(spec.height),
            "math": "0",
            "shadow": "0",
            "background": "#FFFFFF",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    box_map = {b.id: b for b in spec.boxes}
    ordered = [b for b in spec.boxes if b.shape == "container"] + [b for b in spec.boxes if b.shape != "container"]

    for b in ordered:
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": b.id,
                "value": _format_drawio_label(b),
                "style": _box_drawio_style(b),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            {"x": str(b.x), "y": str(b.y), "width": str(b.w), "height": str(b.h), "as": "geometry"},
        )

    for e in spec.edges:
        src_b, dst_b = box_map[e.src], box_map[e.dst]
        s_anc, d_anc = _auto_anchors(src_b, dst_b)
        if e.src_anchor != "auto":
            s_anc = e.src_anchor
        if e.dst_anchor != "auto":
            d_anc = e.dst_anchor

        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
            f"strokeColor={e.color};strokeWidth={e.stroke_width};endArrow=classic;endFill=1;"
            f"fontFamily={FONT_FAMILY};fontSize=10;fontColor=#2D3748;labelBackgroundColor=#FFFFFF;"
            + _drawio_anchor_style(s_anc, "exit")
            + _drawio_anchor_style(d_anc, "entry")
        )
        if e.dashed:
            style += "dashed=1;dashPattern=5 3;"
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": e.id,
                "value": html.escape(e.label),
                "style": style,
                "edge": "1",
                "parent": "1",
                "source": e.src,
                "target": e.dst,
            },
        )
        geom = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        if e.waypoints:
            arr = ET.SubElement(geom, "Array", {"as": "points"})
            for wx, wy in e.waypoints:
                ET.SubElement(arr, "mxPoint", {"x": str(wx), "y": str(wy)})

    if spec.footnote:
        fn = ET.SubElement(
            root,
            "mxCell",
            {
                "id": "footnote",
                "value": html.escape(spec.footnote),
                "style": f"text;html=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;fontSize=10;fontColor=#6C757D;fontFamily={FONT_FAMILY};",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            fn,
            "mxGeometry",
            {"x": "20", "y": str(spec.height - 26), "width": str(spec.width - 40), "height": "20", "as": "geometry"},
        )

    ET.indent(mxfile, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(mxfile, encoding="unicode") + "\n"


def build_svg(spec: DiagramSpec) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{spec.width}" height="{spec.height}" viewBox="0 0 {spec.width} {spec.height}">',
        "  <defs>",
    ]
    for c in sorted({e.color for e in spec.edges}):
        cid = c.lstrip("#")
        parts.append(
            f'    <marker id="arr-{cid}" viewBox="0 0 10 10" refX="8.5" refY="5" '
            f'markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">'
            f'<path d="M 0 1.8 L 9 5 L 0 8.2 z" fill="{c}"/></marker>'
        )
    parts.append("  </defs>")
    parts.append(f'  <rect x="0" y="0" width="{spec.width}" height="{spec.height}" fill="#FFFFFF"/>')

    box_map = {b.id: b for b in spec.boxes}
    ordered = [b for b in spec.boxes if b.shape == "container"] + [b for b in spec.boxes if b.shape != "container"]

    for b in ordered:
        fill, stroke, font_color = PALETTE[b.theme]
        dash = ' stroke-dasharray="5,3"' if b.dashed else ""
        if b.shape == "diamond":
            cx, cy = b.x + b.w / 2, b.y + b.h / 2
            pts = f"{cx:.1f},{b.y} {b.x+b.w},{cy:.1f} {cx:.1f},{b.y+b.h} {b.x},{cy:.1f}"
            parts.append(
                f'  <polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{b.stroke_width}"{dash}/>'
            )
        elif b.shape == "cylinder":
            rx, ry = b.w / 2, 7.5
            parts.append(
                f'  <path d="M {b.x} {b.y+ry} A {rx} {ry} 0 0 1 {b.x+b.w} {b.y+ry} '
                f'L {b.x+b.w} {b.y+b.h-ry} A {rx} {ry} 0 0 1 {b.x} {b.y+b.h-ry} Z" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{b.stroke_width}"{dash}/>'
            )
            parts.append(
                f'  <ellipse cx="{b.x+rx}" cy="{b.y+ry}" rx="{rx}" ry="{ry}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{b.stroke_width}"/>'
            )
        elif b.shape != "note":
            rx = 3 if b.shape == "container" else 4
            parts.append(
                f'  <rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="{rx}" ry="{rx}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{b.stroke_width}"{dash}/>'
            )

        lines = b.label.split("\n")
        line_h = b.font_size * 1.42
        if b.shape == "container":
            parts.append(
                f'  <text x="{b.x + 10}" y="{b.y + 18}" text-anchor="start" '
                f'font-family="{FONT_FAMILY}" font-size="{b.font_size}" font-weight="600" fill="{font_color}">'
                f'{html.escape(lines[0])}</text>'
            )
        else:
            total_h = (len(lines) - 1) * line_h
            start_y = b.y + b.h / 2 - total_h / 2 + b.font_size * 0.35
            if b.shape == "cylinder":
                start_y += 4
            anchor = "start" if b.align == "left" else "middle"
            tx = b.x + 10 if b.align == "left" else b.x + b.w / 2
            for idx, line in enumerate(lines):
                is_title = (idx == 0 and b.bold_first)
                fw = "600" if is_title else "400"
                fs = b.font_size if idx == 0 else max(9.5, b.font_size - 1)
                col = font_color if idx == 0 else "#4A5568"
                parts.append(
                    f'  <text x="{tx:.1f}" y="{start_y + idx * line_h:.1f}" text-anchor="{anchor}" '
                    f'font-family="{FONT_FAMILY}" font-size="{fs}" font-weight="{fw}" fill="{col}">'
                    f'{html.escape(line)}</text>'
                )

    for e in spec.edges:
        src_b, dst_b = box_map[e.src], box_map[e.dst]
        s_anc, d_anc = _auto_anchors(src_b, dst_b)
        if e.src_anchor != "auto":
            s_anc = e.src_anchor
        if e.dst_anchor != "auto":
            d_anc = e.dst_anchor
        p0 = _anchor_point(src_b, s_anc)
        p1 = _anchor_point(dst_b, d_anc)
        pts: list[tuple[float, float]] = [p0]
        if e.waypoints:
            pts.extend((float(wx), float(wy)) for wx, wy in e.waypoints)
        elif abs(p0[0] - p1[0]) > 2 and abs(p0[1] - p1[1]) > 2:
            if s_anc in ("left", "right") and d_anc in ("left", "right"):
                mx = (p0[0] + p1[0]) / 2
                pts.extend([(mx, p0[1]), (mx, p1[1])])
            elif s_anc in ("top", "bottom") and d_anc in ("top", "bottom"):
                my = (p0[1] + p1[1]) / 2
                pts.extend([(p0[0], my), (p1[0], my)])
            elif s_anc in ("left", "right") and d_anc in ("top", "bottom"):
                pts.append((p1[0], p0[1]))
            else:
                pts.append((p0[0], p1[1]))
        pts.append(p1)

        d_str = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        dash = ' stroke-dasharray="5,3"' if e.dashed else ""
        cid = e.color.lstrip("#")
        parts.append(
            f'  <path d="{d_str}" fill="none" stroke="{e.color}" stroke-width="{e.stroke_width}"{dash} marker-end="url(#arr-{cid})"/>'
        )
        if e.label:
            seg = e.label_seg if e.label_seg is not None else max(
                range(len(pts) - 1),
                key=lambda i: math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]),
            )
            lx = (pts[seg][0] + pts[seg + 1][0]) / 2 + e.label_offset[0]
            ly = (pts[seg][1] + pts[seg + 1][1]) / 2 + e.label_offset[1]
            est_w = max(28, sum(10 if ord(ch) > 127 else 6 for ch in e.label) + 10)
            parts.append(
                f'  <rect x="{lx - est_w/2:.1f}" y="{ly - 10:.1f}" width="{est_w:.1f}" height="14" '
                f'rx="2" fill="#FFFFFF" fill-opacity="0.95"/>'
            )
            parts.append(
                f'  <text x="{lx:.1f}" y="{ly + 0.5:.1f}" text-anchor="middle" '
                f'font-family="{FONT_FAMILY}" font-size="9.8" fill="{e.color}">{html.escape(e.label)}</text>'
            )

    if spec.footnote:
        parts.append(
            f'  <text x="20" y="{spec.height - 12}" text-anchor="start" '
            f'font-family="{FONT_FAMILY}" font-size="9.8" fill="#6C757D">{html.escape(spec.footnote)}</text>'
        )

    parts.append("</svg>\n")
    return "\n".join(parts)


def make_fig1_architecture() -> DiagramSpec:
    """Compact IEEE/USENIX-style 3-zone system architecture (Modules A-F)."""
    boxes = [
        # Three clean dashed containers
        Box("c_off", 20, 18, 224, 412, "(a) 离线基线与索引层", "container", "container", 1.0, True, 11),
        Box("c_on", 268, 18, 536, 412, "(b) 在线三层筛查与受控生成", "container", "container", 1.0, True, 11),
        Box("c_ev", 828, 18, 192, 412, "(c) 审计与评价层", "container", "container", 1.0, True, 11),

        # Offline
        Box("m_a", 36, 56, 192, 74, "知识库构建 (模块 A)\n50 Linux 事实 · 400 正常文档\n200 投毒 (I1/I2 注入, F1/F2 错事实)", "neutral", "roundrect", 1.2, False, 10.5),
        Box("m_b", 36, 166, 192, 74, "SHA-256 基线清单 (模块 B)\n仅含 doc_id → sha256(text)\n不含标签与来源属性", "subtle", "cylinder", 1.2, False, 10.5),
        Box("m_idx", 36, 276, 192, 66, "语义检索索引 (模块 E)\nbge-small-zh-v1.5\n离线自动回退 TF-IDF", "neutral", "roundrect", 1.2, False, 10.5),
        Box("m_cfg", 36, 364, 192, 48, "冻结配置 (seed=42)\n阈值 · 组别 · 模型快照", "subtle", "roundrect", 1.0, True, 10),

        # Online
        Box("q_in", 290, 56, 174, 52, "用户查询输入\n24 冻结 / 97 开发 / 56 API", "neutral", "roundrect", 1.2, False, 10.5),
        Box("topk", 520, 56, 260, 52, "Top-5 候选文档检索\n返回 (doc_id, text, source, score)", "neutral", "roundrect", 1.2, False, 10.5),

        # Three core defense modules (single muted slate-blue accent)
        Box("d_int", 290, 148, 152, 74, "① 完整性校验\nsrc/integrity.py\npass / fail / missing", "accent", "roundrect", 1.6, False, 10.5),
        Box("d_prv", 464, 148, 152, 74, "② 来源评估 (模块 C)\nsrc/provenance.py\n白名单 / 未列 / 未知", "accent", "roundrect", 1.6, False, 10.5),
        Box("d_sem", 638, 148, 148, 74, "③ 语义检测 (模块 D)\nQwen2.5-1.5B (split-v6)\n指令 + 事实双分支", "accent", "roundrect", 1.6, False, 10.5),

        Box("gate", 482, 252, 116, 56, "处置网关", "decision", "diamond", 1.3, False, 10.5),
        Box("blk", 648, 256, 138, 48, "拦截排除出上下文\nreview / quarantine", "alert", "roundrect", 1.3, False, 10.2),

        Box("ctx", 290, 336, 226, 74, "受控上下文构建\n仅 allow 文档 (≤3600 字符)\n默认：完整段落 (候选：重排/标记)", "neutral", "roundrect", 1.2, False, 10.2),
        Box("gen", 554, 336, 232, 74, "受控生成 (模块 E)\nQwen2.5-1.5B-Instruct (FP16)\n数据指令隔离；空上下文→拒答", "accent", "roundrect", 1.4, False, 10.2),

        # Audit & evaluation
        Box("log", 844, 56, 160, 74, "全链路审计日志\nraw.jsonl / detect_eval\n处置 · 缓存 · 分阶段耗时", "subtle", "cylinder", 1.2, False, 10.2),
        Box("met", 844, 166, 160, 72, "离线指标重算 (模块 F)\nASR · 正确率 · P/R/F1\nFPR · 误伤 · P95 时延", "neutral", "roundrect", 1.2, False, 10.2),
        Box("iso", 844, 286, 160, 124, "评价隔离边界\nevaluation_only\nlabel · attack_type · payload\n严禁进入检测与生成输入", "boundary", "roundrect", 1.5, True, 10.2),
    ]

    edges = [
        Edge("e1", "m_a", "m_b", "", "#343A40", False, 1.2, "bottom", "top"),
        Edge("e2", "m_b", "m_idx", "", "#343A40", False, 1.2, "bottom", "top"),
        Edge("e3", "m_b", "d_int", "基线查验", "#2C5282", True, 1.2, "right", "left", [(258, 203), (258, 185)], label_offset=(-2, -11), label_seg=2),
        Edge("e4", "m_idx", "topk", "索引召回", "#495057", True, 1.1, "right", "bottom", [(248, 309), (248, 128), (650, 128)], label_offset=(-145, -8), label_seg=2),
        Edge("e5", "q_in", "topk", "", "#343A40", False, 1.2, "right", "left"),
        Edge("e6", "topk", "d_int", "Top-5", "#343A40", False, 1.2, "bottom", "top", [(650, 128), (366, 128)], label_offset=(0, -8), label_seg=1),
        Edge("e7", "d_int", "d_prv", "pass", "#2C5282", False, 1.3, "right", "left"),
        Edge("e8", "d_prv", "d_sem", "allow", "#2C5282", False, 1.3, "right", "left"),
        Edge("e9", "d_sem", "gate", "", "#2C5282", False, 1.3, "bottom", "top", [(712, 236), (540, 236)]),
        Edge("e10", "gate", "blk", "拦截", "#9B2C2C", False, 1.2, "right", "left"),
        Edge("e11", "gate", "ctx", "allow", "#2C5282", False, 1.3, "left", "top", [(403, 280)], label_offset=(0, -8), label_seg=0),
        Edge("e12", "ctx", "gen", "", "#343A40", False, 1.2, "right", "left"),
        Edge("e13", "gen", "log", "写入审计", "#343A40", False, 1.2, "right", "left", [(814, 373), (814, 93)], label_offset=(0, 0), label_seg=1),
        Edge("e14", "log", "met", "", "#343A40", False, 1.2, "bottom", "top"),
        Edge("e15", "iso", "met", "离线核验", "#9B2C2C", True, 1.2, "top", "bottom", label_offset=(30, 0)),
    ]

    return DiagramSpec(
        slug="fig1_system_architecture",
        name="图1_系统总体架构",
        width=1040,
        height=460,
        boxes=boxes,
        edges=edges,
        footnote="注：浅蓝框表示核心防御与受控生成模块；红色虚线框标示评价真值隔离边界（evaluation_only），仅离线指标重算可访问。",
    )


def make_fig2_defense_flow() -> DiagramSpec:
    """Compact left-to-right + branched decision flowchart for Combined defense & dual-branch detector."""
    boxes = [
        Box("c_sem", 542, 22, 476, 272, "层 3：双分支语义检测 (Qwen2.5-1.5B, split-v6, ≤32 tokens, 失败重试 1 次)", "container", "container", 1.1, True, 10.5),

        Box("in_d", 20, 74, 114, 56, "Top-5 候选文档\ndoc_id · text · source", "neutral", "roundrect", 1.2, False, 10.2),

        Box("s1", 162, 74, 126, 56, "① SHA-256 校验\nverify(doc, manifest)", "accent", "roundrect", 1.5, False, 10.2),
        Box("d1", 180, 166, 90, 56, "哈希状态", "decision", "diamond", 1.3, False, 10.2),

        Box("s2", 336, 74, 134, 56, "② 来源规则评估\nprovenance.assess", "accent", "roundrect", 1.5, False, 10.2),
        Box("d2", 358, 166, 90, 56, "白名单?", "decision", "diamond", 1.3, False, 10.2),

        # Semantic detector internals
        Box("cache", 564, 74, 108, 56, "缓存命中?", "decision", "diamond", 1.2, False, 10.2),
        Box("b1", 724, 52, 276, 56, "分支 1：行为指令判断\nattack(0.90) | unclear(0.55) | quoted(0.25) | none(0.02)", "accent", "roundrect", 1.4, False, 10),
        Box("b2", 724, 126, 276, 56, "分支 2：事实一致性（仅读 text + trusted_ref）\ncontradicted(0.85) | insufficient(0.50) | supported(0.05)", "accent", "roundrect", 1.4, False, 10),
        Box("agg", 564, 212, 436, 58, "风险聚合与写缓存：risk_score = max(s1, s2)\n键控：(prompt_ver + text + ref)；修复后仍失败则回退 review", "subtle", "roundrect", 1.2, False, 10.2),

        # Bottom decision row
        Box("d3", 718, 320, 128, 56, "阈值判定\n0.70 / 0.40", "decision", "diamond", 1.3, False, 10.2),
        Box("allow", 654, 412, 256, 54, "放行 (allow, risk_score < 0.40)\n拼入 [doc_id] text 数据区；全空则拒答", "accent", "roundrect", 1.5, False, 10.2),
        Box("block", 162, 326, 308, 140, "拦截并排除出生成上下文（保守策略）\n• 哈希 fail → quarantine（直接短路）\n• 哈希 missing → review\n• 来源未列 (distro_wiki) / 未知 / 伪冒 → review\n• 语义 risk_score ≥ 0.70 → quarantine\n• 语义 0.40 ≤ risk_score < 0.70 → review", "alert", "roundrect", 1.3, False, 10, align="left"),
    ]

    edges = [
        Edge("e1", "in_d", "s1", "", "#343A40", False, 1.2, "right", "left"),
        Edge("e2", "s1", "d1", "", "#2C5282", False, 1.2, "bottom", "top"),
        Edge("e3", "d1", "block", "fail / missing", "#9B2C2C", False, 1.2, "bottom", "top", [(225, 306), (316, 306)], label_offset=(42, 0), label_seg=0),
        Edge("e4", "d1", "s2", "pass", "#2C5282", False, 1.3, "right", "left", [(308, 194), (308, 102)], label_offset=(-18, -8), label_seg=0),
        Edge("e5", "s2", "d2", "", "#2C5282", False, 1.2, "bottom", "top"),
        Edge("e6", "d2", "block", "否 (review)", "#9B2C2C", False, 1.2, "bottom", "top", [(403, 306), (316, 306)], label_offset=(36, 0), label_seg=0),
        Edge("e7", "d2", "cache", "trusted", "#2C5282", False, 1.3, "right", "left", [(504, 194), (504, 102)], label_offset=(-20, -8), label_seg=0),
        Edge("e8", "cache", "b1", "未命中", "#2C5282", False, 1.2, "right", "left", [(698, 102), (698, 80)], label_offset=(-8, -10), label_seg=0),
        Edge("e9", "cache", "b2", "", "#2C5282", False, 1.2, "right", "left", [(698, 102), (698, 154)]),
        Edge("e10", "cache", "agg", "命中 (0 s)", "#495057", True, 1.2, "bottom", "top", [(618, 196), (782, 196)], label_offset=(34, 0), label_seg=0),
        Edge("e11", "b1", "agg", "", "#2C5282", False, 1.1, "right", "top", [(1009, 80), (1009, 196), (782, 196)]),
        Edge("e12", "b2", "agg", "", "#2C5282", False, 1.1, "bottom", "top", [(862, 196), (782, 196)]),
        Edge("e13", "agg", "d3", "", "#343A40", False, 1.2, "bottom", "top"),
        Edge("e14", "d3", "block", "≥ 0.40", "#9B2C2C", False, 1.3, "left", "right", [(594, 348), (594, 396)], label_offset=(0, -8), label_seg=0),
        Edge("e15", "d3", "allow", "< 0.40", "#2C5282", False, 1.4, "bottom", "top", label_offset=(26, 0)),
    ]

    return DiagramSpec(
        slug="fig2_defense_decision_flow",
        name="图2_组合防护决策流程",
        width=1040,
        height=498,
        boxes=boxes,
        edges=edges,
        footnote="注：组合防护采用顺序短路策略，仅前一层放行（allow）的候选文档才进入本地 1.5B 语义检测；所有阈值均在实验前写入配置冻结。",
    )


def make_fig3_threat_model() -> DiagramSpec:
    """Two-lane academic comparison of post_ingestion vs pre_ingestion threat models."""
    boxes = [
        Box("c_atk", 20, 18, 250, 368, "攻击者能力与投毒载荷", "container", "container", 1.0, True, 10.5),
        Box("c_post", 294, 18, 706, 172, "(a) post_ingestion：入库建基线后篡改", "container", "container", 1.0, True, 10.5),
        Box("c_pre", 294, 214, 706, 172, "(b) pre_ingestion：入库前供应链投毒", "container", "container", 1.0, True, 10.5),

        # Attacker column
        Box("a1", 36, 56, 218, 78, "恒定规模同 ID 替换\n语料恒为 400 条 (5% / 10% / 20%)\n可伪造声明式 source 字段", "neutral", "roundrect", 1.2, False, 10.2, align="left"),
        Box("a2", 36, 152, 218, 74, "提示注入载荷 (100 条)\nI1：定向改写技术结论\nI2：诱导输出哨兵 RAG_POISON_999", "alert", "roundrect", 1.2, False, 10.2, align="left"),
        Box("a3", 36, 244, 218, 74, "错误技术事实 (100 条)\nF1 / F2：颠倒 Linux 系统调用语义\n无显式指令词，关键词规则难拦截", "alert", "roundrect", 1.2, False, 10.2, align="left"),
        Box("a4", 36, 334, 218, 36, "约束：不可篡改已落盘基线与评价真值", "boundary", "roundrect", 1.2, True, 9.8, bold_first=False),

        # Post-ingestion lane
        Box("p1", 314, 68, 132, 60, "1. 干净语料入库\n400 条正常文档", "neutral", "roundrect", 1.2, False, 10.2),
        Box("p2", 476, 68, 140, 60, "2. 建立基线清单\n记录干净 SHA-256", "subtle", "cylinder", 1.2, False, 10.2),
        Box("p3", 646, 68, 140, 60, "3. 攻击者替换文档\n字节改变 (同 doc_id)", "alert", "roundrect", 1.3, False, 10.2),
        Box("p4", 816, 62, 166, 72, "4. 哈希检出 100%\n16/16 · 28/28 · 55/55\nASR = 0（正确率 83.3%）", "accent", "roundrect", 1.5, False, 10.2),
        Box("pn", 314, 148, 668, 28, "结论：字节级哈希对入库后篡改零漏报且低开销，但无法验证入库前内容真实性。", "note", "note", 0, False, 9.8, bold_first=False, align="left"),

        # Pre-ingestion lane
        Box("r1", 314, 258, 132, 62, "1. 投毒文档混入\n含伪造 man_pages", "alert", "roundrect", 1.3, False, 10.2),
        Box("r2", 476, 258, 140, 62, "2. 后建基线清单\n基线含投毒文本", "subtle", "cylinder", 1.2, False, 10.2),
        Box("r3", 646, 258, 140, 62, "3. 哈希检出 0%\nintegrity 组退化为\nbaseline (ASR 65%)", "alert", "roundrect", 1.3, True, 10.2),
        Box("r4", 816, 252, 166, 74, "4. 来源 + 语义互补\n来源 31/55 · 语义 24/55\nASR = 0（14 正常转复核）", "accent", "roundrect", 1.5, False, 10.2),
        Box("rn", 314, 340, 668, 30, "结论：入库前投毒必须依赖来源规则与语义检测互补拦截；保守来源白名单带来覆盖率代价。", "note", "note", 0, False, 9.8, bold_first=False, align="left"),
    ]

    edges = [
        Edge("e1", "p1", "p2", "", "#343A40", False, 1.2, "right", "left"),
        Edge("e2", "p2", "p3", "", "#9B2C2C", False, 1.2, "right", "left"),
        Edge("e3", "p3", "p4", "fail", "#2C5282", False, 1.3, "right", "left"),
        Edge("e4", "r1", "r2", "", "#343A40", False, 1.2, "right", "left"),
        Edge("e5", "r2", "r3", "pass", "#9B2C2C", False, 1.2, "right", "left"),
        Edge("e6", "r3", "r4", "联防", "#2C5282", False, 1.3, "right", "left"),
        Edge("e7", "a2", "p3", "", "#9B2C2C", True, 1.1, "right", "top", [(282, 189), (282, 50), (716, 50)]),
        Edge("e8", "a3", "r1", "", "#9B2C2C", True, 1.1, "right", "left", [(282, 281), (282, 289)]),
    ]

    return DiagramSpec(
        slug="fig3_threat_model_scenes",
        name="图3_威胁模型与场景对照",
        width=1020,
        height=416,
        boxes=boxes,
        edges=edges,
        footnote="注：图中括号内计数（55/55、31/55、24/55）对应 20% 投毒比例下 24 道冻结查询实际检索到的恶意文档总数。",
    )


def make_fig4_evolution() -> DiagramSpec:
    """Clean 2-row 6-stage scientific iteration & failure-driven pivot diagram."""
    boxes = [
        Box("s1", 20, 22, 286, 134, "阶段 1：正式轮四组对照（768 查询）\n• 组合防护将 ASR 由 0.650 压至 0.000\n• 检测器 P=0.976 / R=1.000 / FPR=0.63%\n• 暴露：14 条 distro_wiki 转复核致正确率 −16.7%", "neutral", "roundrect", 1.2, False, 10.2, align="left"),
        Box("s2", 386, 22, 286, 134, "阶段 2：证据粒度四条件消融（388 条）\n• 97 开发题对比句子抽取与完整段落\n• 原开发 AI 暂判：句子 42/47 vs 段落 67/72\n• 结论：完整段落避免撕裂条件，净增 +25 题", "neutral", "roundrect", 1.2, False, 10.2, align="left"),
        Box("s3", 752, 22, 286, 134, "阶段 3：API 挑战与 GPT-6 复核（224 条）\n• 8 事实簇 × 7 场景 = 56 题（98 项复核）\n• 联合口径：段落不滤 27/56 > 过滤 22/56\n• 失败：全文过滤误杀 8/8 合法引用样例", "neutral", "roundrect", 1.2, False, 10.2, align="left"),

        Box("s4", 20, 206, 286, 144, "阶段 4：语义门控 v1（153 条 · 负面实验）\n• 133 次 1.5B 调用全部拒答（覆盖率 0%）\n• 24 次正负/反转编码/自由解码诊断确认\n  非单纯约束解码问题 → 止损不并入默认", "alert", "roundrect", 1.4, True, 10.2, align="left"),
        Box("s5", 386, 206, 286, 144, "阶段 5：BGE 重排与句界标记（612 条）\n• 40 对探针：复述 8/8、错事实 6/8 过高分\n  → 禁止相关性阈值作充分性/事实门槛\n• 44 项补评：API 32/56 (+5/0退)，开发 66/97", "neutral", "roundrect", 1.2, False, 10.2, align="left"),
        Box("s6", 752, 206, 286, 144, "最终工程冻结决策\n• 默认：三层可审计筛查 + 完整段落\n• 优先候选：重排+标记（待做 2×2 因子消融）\n• 排除：全局禁止词 / 语义门控 v1 / 硬阈值\n• 后续：新建 ≥24 个未见事实簇验证", "accent", "roundrect", 1.6, False, 10.2, align="left"),
    ]

    edges = [
        Edge("e1", "s1", "s2", "诊断覆盖率", "#343A40", False, 1.2, "right", "left"),
        Edge("e2", "s2", "s3", "压力测试", "#343A40", False, 1.2, "right", "left"),
        Edge("e3", "s3", "s4", "尝试语义门控", "#9B2C2C", False, 1.2, "bottom", "top", [(895, 182), (163, 182)], label_offset=(0, -8), label_seg=1),
        Edge("e4", "s4", "s5", "止损转向重排", "#9B2C2C", True, 1.2, "right", "left"),
        Edge("e5", "s5", "s6", "核验冻结", "#2C5282", False, 1.4, "right", "left"),
    ]

    return DiagramSpec(
        slug="fig4_experiment_evolution_flow",
        name="图4_五阶段实验演进与决策闭环",
        width=1058,
        height=388,
        boxes=boxes,
        edges=edges,
        footnote="注：不同阶段的数据集与裁判口径（规则评分 / 原开发 AI 暂判 / GPT-6 事后联合口径 / 模型辅助溯源补评）严格分开统计，不跨表混算。",
    )


def validate_no_foreground_overlap(spec: DiagramSpec) -> None:
    fg = [b for b in spec.boxes if b.shape not in ("container", "note")]
    for i in range(len(fg)):
        for j in range(i + 1, len(fg)):
            a, b = fg[i], fg[j]
            ox = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
            oy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
            if ox > 0 and oy > 0:
                raise AssertionError(f"[{spec.slug}] Box overlap between {a.id} and {b.id}: {ox}x{oy}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = [
        make_fig1_architecture(),
        make_fig2_defense_flow(),
        make_fig3_threat_model(),
        make_fig4_evolution(),
    ]
    for spec in specs:
        validate_no_foreground_overlap(spec)
        drawio_xml = build_drawio_xml(spec)
        ET.fromstring(drawio_xml)
        (OUT_DIR / f"{spec.slug}.drawio").write_text(drawio_xml, encoding="utf-8")

        svg_xml = build_svg(spec)
        ET.fromstring(svg_xml)
        (OUT_DIR / f"{spec.slug}.svg").write_text(svg_xml, encoding="utf-8")
        print(f"Generated: docs/diagrams/{spec.slug}.drawio & .svg ({spec.width}x{spec.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
