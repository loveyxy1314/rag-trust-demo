#!/usr/bin/env python3
"""Generate academic-grade draw.io (.drawio) diagrams and matching true-text SVG previews.

Color palette & styling follow a Science-style colorblind-friendly academic palette:
  - Blue   (#4E79A7 / fill #EBF2F7): Input / Output / Data processing
  - Orange (#F28E2B / fill #FEF3E6): Core defense / algorithm steps (bold border)
  - Green  (#59A14F / fill #EDF6EC): Trusted storage / allow / verified output
  - Yellow (#EDC948 / fill #FDF9E7): Decision gates (diamond)
  - Red    (#E15759 / fill #FDECEC): Attacks / quarantine / review / negative results
  - Gray   (#6C757D / fill #F4F5F7): Swimlanes / auxiliary containers
  - Dashed Red (#CC3311): Security & evaluation isolation boundaries

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

FONT_FAMILY = "Microsoft YaHei, PingFang SC, Helvetica, Arial, sans-serif"

PALETTE = {
    "blue": ("#EBF2F7", "#4E79A7", "#1F3B57"),
    "orange": ("#FEF3E6", "#F28E2B", "#7A4100"),
    "green": ("#EDF6EC", "#59A14F", "#24541E"),
    "yellow": ("#FDF9E7", "#D4A017", "#6B4E00"),
    "red": ("#FDECEC", "#E15759", "#7F1D1D"),
    "gray": ("#F4F5F7", "#6C757D", "#2D3436"),
    "teal": ("#EAF5F4", "#76B7B2", "#1F4E4A"),
    "purple": ("#F4EFF5", "#B07AA1", "#4A2545"),
    "boundary": ("#FFF7F7", "#CC3311", "#A61C00"),
}


@dataclass
class Box:
    id: str
    x: int
    y: int
    w: int
    h: int
    label: str
    theme: str = "blue"
    shape: str = "roundrect"  # roundrect | diamond | container | cylinder | banner
    stroke_width: float = 1.5
    dashed: bool = False
    font_size: int = 12
    bold: bool = False
    align: str = "center"  # center | left


@dataclass
class Edge:
    id: str
    src: str
    dst: str
    label: str = ""
    color: str = "#495057"
    dashed: bool = False
    stroke_width: float = 1.5
    src_anchor: str = "auto"  # top | bottom | left | right | auto
    dst_anchor: str = "auto"
    waypoints: list[tuple[int, int]] = field(default_factory=list)
    label_offset: tuple[int, int] = (0, -8)


@dataclass
class DiagramSpec:
    slug: str
    title: str
    subtitle: str
    width: int
    height: int
    boxes: list[Box]
    edges: list[Edge]
    legend_items: list[tuple[str, str, bool]]  # (theme, label, dashed)


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
    mapping = {
        "top": (0.5, 0.0),
        "bottom": (0.5, 1.0),
        "left": (0.0, 0.5),
        "right": (1.0, 0.5),
    }
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
    if box.bold:
        parts.append("fontStyle=1")
    if box.dashed:
        parts.append("dashed=1")
        parts.append("dashPattern=6 4")

    if box.shape == "diamond":
        parts.insert(0, "rhombus")
    elif box.shape == "cylinder":
        parts.insert(0, "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10")
    elif box.shape == "container":
        parts.insert(0, "rounded=1;arcSize=6")
        parts.extend(["verticalAlign=top", "align=left", "spacingTop=6", "spacingLeft=10"])
    elif box.shape == "banner":
        parts.insert(0, "rounded=0")
        parts.extend(["strokeColor=none", "fillColor=none"])
    else:
        parts.insert(0, "rounded=1;arcSize=12")
        if box.align == "left":
            parts.extend(["align=left", "spacingLeft=10", "spacingRight=8"])
    return ";".join(parts) + ";"


def build_drawio_xml(spec: DiagramSpec) -> str:
    mxfile = ET.Element(
        "mxfile",
        {
            "host": "app.diagrams.net",
            "agent": "rag-trust-demo/generate_diagrams.py",
            "version": "24.7.17",
        },
    )
    diagram = ET.SubElement(mxfile, "diagram", {"id": spec.slug, "name": spec.title})
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1200",
            "dy": "800",
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

    # Title + subtitle cells
    title_cell = ET.SubElement(
        root,
        "mxCell",
        {
            "id": "title_main",
            "value": f"<b>{html.escape(spec.title)}</b>",
            "style": f"text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=0;strokeColor=none;fillColor=none;fontSize=18;fontColor=#1D3557;fontFamily={FONT_FAMILY};",
            "vertex": "1",
            "parent": "1",
        },
    )
    ET.SubElement(
        title_cell,
        "mxGeometry",
        {"x": "20", "y": "12", "width": str(spec.width - 40), "height": "30", "as": "geometry"},
    )

    sub_cell = ET.SubElement(
        root,
        "mxCell",
        {
            "id": "title_sub",
            "value": html.escape(spec.subtitle),
            "style": f"text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=0;strokeColor=none;fillColor=none;fontSize=11;fontColor=#5A626A;fontFamily={FONT_FAMILY};",
            "vertex": "1",
            "parent": "1",
        },
    )
    ET.SubElement(
        sub_cell,
        "mxGeometry",
        {"x": "20", "y": "42", "width": str(spec.width - 40), "height": "22", "as": "geometry"},
    )

    box_map = {b.id: b for b in spec.boxes}

    # Draw containers first so foreground boxes appear above them
    ordered_boxes = [b for b in spec.boxes if b.shape == "container"] + [
        b for b in spec.boxes if b.shape != "container"
    ]
    for b in ordered_boxes:
        val = "<br>".join(html.escape(line) for line in b.label.split("\n"))
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": b.id,
                "value": val,
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

    # Edges
    for e in spec.edges:
        src_b, dst_b = box_map[e.src], box_map[e.dst]
        s_anc, d_anc = _auto_anchors(src_b, dst_b)
        if e.src_anchor != "auto":
            s_anc = e.src_anchor
        if e.dst_anchor != "auto":
            d_anc = e.dst_anchor

        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
            f"strokeColor={e.color};strokeWidth={e.stroke_width};endArrow=block;endFill=1;"
            f"fontFamily={FONT_FAMILY};fontSize=11;fontColor=#2D3436;labelBackgroundColor=#FFFFFF;"
            + _drawio_anchor_style(s_anc, "exit")
            + _drawio_anchor_style(d_anc, "entry")
        )
        if e.dashed:
            style += "dashed=1;dashPattern=6 4;"
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

    # Legend bar at bottom
    ly = spec.height - 42
    lx = 30
    item_w = max(145, (spec.width - 60) // max(1, len(spec.legend_items)))
    for idx, (theme, text, dashed) in enumerate(spec.legend_items):
        fill, stroke, _ = PALETTE[theme]
        sw = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"legend_box_{idx}",
                "value": "",
                "style": f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;{'dashed=1;' if dashed else ''}",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            sw,
            "mxGeometry",
            {"x": str(lx + idx * item_w), "y": str(ly + 6), "width": "22", "height": "14", "as": "geometry"},
        )
        lbl = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"legend_lbl_{idx}",
                "value": html.escape(text),
                "style": f"text;html=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;fontSize=11;fontColor=#2D3436;fontFamily={FONT_FAMILY};",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            lbl,
            "mxGeometry",
            {"x": str(lx + idx * item_w + 28), "y": str(ly + 2), "width": str(item_w - 34), "height": "22", "as": "geometry"},
        )

    ET.indent(mxfile, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(mxfile, encoding="unicode") + "\n"


def build_svg(spec: DiagramSpec) -> str:
    """Render matching crisp true-text vector SVG directly from the same DiagramSpec."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{spec.width}" height="{spec.height}" viewBox="0 0 {spec.width} {spec.height}">',
        "  <defs>",
    ]
    # Arrowhead markers for each distinct edge color
    edge_colors = sorted({e.color for e in spec.edges})
    for c in edge_colors:
        cid = c.lstrip("#")
        parts.append(
            f'    <marker id="arrow-{cid}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="{c}"/></marker>'
        )
    parts.append("  </defs>")
    parts.append(f'  <rect x="0" y="0" width="{spec.width}" height="{spec.height}" fill="#FFFFFF"/>')

    # Title and subtitle
    parts.append(
        f'  <text x="{spec.width/2:.1f}" y="33" text-anchor="middle" '
        f'font-family="{FONT_FAMILY}" font-size="18" font-weight="700" fill="#1D3557">'
        f'{html.escape(spec.title)}</text>'
    )
    parts.append(
        f'  <text x="{spec.width/2:.1f}" y="56" text-anchor="middle" '
        f'font-family="{FONT_FAMILY}" font-size="11.5" fill="#5A626A">'
        f'{html.escape(spec.subtitle)}</text>'
    )

    box_map = {b.id: b for b in spec.boxes}
    ordered_boxes = [b for b in spec.boxes if b.shape == "container"] + [
        b for b in spec.boxes if b.shape != "container"
    ]

    for b in ordered_boxes:
        fill, stroke, font_color = PALETTE[b.theme]
        dash = ' stroke-dasharray="6,4"' if b.dashed else ""
        if b.shape == "diamond":
            cx, cy = b.x + b.w / 2, b.y + b.h / 2
            pts = f"{cx},{b.y} {b.x+b.w},{cy} {cx},{b.y+b.h} {b.x},{cy}"
            parts.append(
                f'  <polygon points="{pts}" fill="{fill}" stroke="{stroke}" '
                f'stroke-width="{b.stroke_width}"{dash}/>'
            )
        elif b.shape == "cylinder":
            rx = b.w / 2
            ry = 9
            parts.append(
                f'  <path d="M {b.x} {b.y+ry} '
                f'A {rx} {ry} 0 0 1 {b.x+b.w} {b.y+ry} '
                f'L {b.x+b.w} {b.y+b.h-ry} '
                f'A {rx} {ry} 0 0 1 {b.x} {b.y+b.h-ry} Z" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{b.stroke_width}"{dash}/>'
            )
            parts.append(
                f'  <ellipse cx="{b.x+rx}" cy="{b.y+ry}" rx="{rx}" ry="{ry}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{b.stroke_width}"/>'
            )
        else:
            rx = 6 if b.shape == "container" else 8
            parts.append(
                f'  <rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="{rx}" ry="{rx}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{b.stroke_width}"{dash}/>'
            )

        lines = b.label.split("\n")
        line_h = b.font_size * 1.38
        if b.shape == "container":
            tx = b.x + 12
            ty = b.y + 20
            for idx, line in enumerate(lines):
                fw = "700" if idx == 0 else "400"
                parts.append(
                    f'  <text x="{tx}" y="{ty + idx * line_h:.1f}" text-anchor="start" '
                    f'font-family="{FONT_FAMILY}" font-size="{b.font_size}" font-weight="{fw}" fill="{font_color}">'
                    f'{html.escape(line)}</text>'
                )
        else:
            total_h = (len(lines) - 1) * line_h
            start_y = b.y + b.h / 2 - total_h / 2 + b.font_size * 0.35
            if b.shape == "cylinder":
                start_y += 5
            anchor = "start" if b.align == "left" else "middle"
            tx = b.x + 12 if b.align == "left" else b.x + b.w / 2
            for idx, line in enumerate(lines):
                fw = "700" if (b.bold or (idx == 0 and len(lines) > 1)) else "400"
                fs = b.font_size if idx == 0 else max(10.5, b.font_size - 1)
                parts.append(
                    f'  <text x="{tx:.1f}" y="{start_y + idx * line_h:.1f}" text-anchor="{anchor}" '
                    f'font-family="{FONT_FAMILY}" font-size="{fs}" font-weight="{fw}" fill="{font_color}">'
                    f'{html.escape(line)}</text>'
                )

    # Edges
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
        dash = ' stroke-dasharray="6,4"' if e.dashed else ""
        cid = e.color.lstrip("#")
        parts.append(
            f'  <path d="{d_str}" fill="none" stroke="{e.color}" '
            f'stroke-width="{e.stroke_width}"{dash} marker-end="url(#arrow-{cid})"/>'
        )
        if e.label:
            # Place label on the longest segment
            best_seg = max(
                range(len(pts) - 1),
                key=lambda i: math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]),
            )
            lx = (pts[best_seg][0] + pts[best_seg + 1][0]) / 2 + e.label_offset[0]
            ly = (pts[best_seg][1] + pts[best_seg + 1][1]) / 2 + e.label_offset[1]
            # Subtle white pill background behind edge label for crisp legibility
            est_w = max(36, len(e.label) * 9.5 + 10)
            parts.append(
                f'  <rect x="{lx - est_w/2:.1f}" y="{ly - 11:.1f}" width="{est_w:.1f}" height="16" '
                f'rx="3" fill="#FFFFFF" fill-opacity="0.92"/>'
            )
            parts.append(
                f'  <text x="{lx:.1f}" y="{ly + 1:.1f}" text-anchor="middle" '
                f'font-family="{FONT_FAMILY}" font-size="10.5" font-weight="600" fill="{e.color}">'
                f'{html.escape(e.label)}</text>'
            )

    # Legend bar
    ly = spec.height - 40
    parts.append(f'  <line x1="28" y1="{ly - 8}" x2="{spec.width - 28}" y2="{ly - 8}" stroke="#DEE2E6" stroke-width="1"/>')
    lx = 34
    item_w = max(148, (spec.width - 68) // max(1, len(spec.legend_items)))
    for idx, (theme, text, dashed) in enumerate(spec.legend_items):
        fill, stroke, _ = PALETTE[theme]
        dash = ' stroke-dasharray="4,3"' if dashed else ""
        bx = lx + idx * item_w
        parts.append(
            f'  <rect x="{bx}" y="{ly + 4}" width="22" height="14" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{dash}/>'
        )
        parts.append(
            f'  <text x="{bx + 29}" y="{ly + 15}" text-anchor="start" '
            f'font-family="{FONT_FAMILY}" font-size="11" fill="#2D3436">{html.escape(text)}</text>'
        )

    parts.append("</svg>\n")
    return "\n".join(parts)


def make_fig1_architecture() -> DiagramSpec:
    boxes = [
        # Containers
        Box("c_offline", 28, 76, 300, 560, "离线入库与基线层（模块 A / B / E-Index）", "gray", "container", 1.2, True, 12, True),
        Box("c_online", 352, 76, 650, 560, "在线检索、三层可信筛查与受控生成（模块 B / C / D / E）", "gray", "container", 1.2, True, 12, True),
        Box("c_eval", 1026, 76, 266, 560, "审计与离线评价层（模块 F）", "gray", "container", 1.2, True, 12, True),
        Box("c_iso", 1044, 412, 230, 206, "评价隔离边界（evaluation_only）", "boundary", "container", 2.0, True, 11.5, True),

        # Offline boxes
        Box("a_corpus", 48, 120, 260, 108, "模块 A：知识库与投毒构建\nsrc/dataset.py\n50 Linux 事实 × 8 模板 = 400 正常文档\n200 投毒文档（I1/I2 注入 + F1/F2 错事实）", "blue", "roundrect", 1.5, False, 11.5),
        Box("b_manifest", 48, 272, 260, 96, "模块 B：SHA-256 基线清单\nsrc/integrity.py\n仅存储 doc_id → sha256(text)\n不含 label / source 评价字段", "green", "cylinder", 1.6, False, 11.5),
        Box("e_index", 48, 412, 260, 98, "模块 E：语义检索索引\nsrc/retriever.py\nBAAI/bge-small-zh-v1.5 向量检索\n无 GPU 时自动回退 TF-IDF", "blue", "roundrect", 1.5, False, 11.5),
        Box("cfg_box", 48, 540, 260, 76, "冻结配置与随机种子\nconfigs/config.yaml (seed=42)\n阈值 / 组别 / 场景 / 快照集中管理", "teal", "roundrect", 1.3, False, 11),

        # Online boxes
        Box("q_in", 378, 118, 228, 72, "用户问题输入\n24 冻结题 / 97 开发题 / 56 API 挑战题", "blue", "roundrect", 1.6, False, 11.5, True),
        Box("ret_topk", 648, 118, 326, 72, "Top-5 候选文档检索\n返回 (doc_id, text, source, retrieval_score)", "blue", "roundrect", 1.5, False, 11.5),

        Box("g_integrity", 378, 234, 182, 92, "层 1：完整性校验\nsrc/integrity.py\n比对 SHA-256 基线\npass / fail / missing", "orange", "roundrect", 2.2, False, 11.5),
        Box("g_prov", 584, 234, 182, 92, "层 2：来源规则评估\nsrc/provenance.py\n白名单 / 未列 / 未知 / 伪冒\nallow / review", "orange", "roundrect", 2.2, False, 11.5),
        Box("g_sem", 790, 234, 184, 92, "层 3：双分支语义检测\nsrc/semantic_detector.py\nQwen2.5-1.5B (split-v6)\n行为指令 + 事实一致性", "orange", "roundrect", 2.2, False, 11.5),

        Box("gate_dec", 590, 368, 170, 82, "最终处置决策\nallow / review /\nquarantine", "yellow", "diamond", 1.8, False, 11.5, True),
        Box("block_box", 802, 376, 172, 66, "拦截并排除出上下文\nreview & quarantine\n保守策略不送入生成器", "red", "roundrect", 1.6, False, 11),

        Box("ctx_box", 378, 492, 276, 112, "受控上下文构建与可选扩展\n仅 allow 文档（≤3600 字符）\n默认：完整段落证据（src/paragraph_selector.py）\n候选扩展：BGE 重排 / 句界数据标记", "green", "roundrect", 1.6, False, 11),
        Box("gen_box", 696, 492, 278, 112, "受控生成与程序拒答\nsrc/rag_pipeline.py\nQwen2.5-1.5B-Instruct (FP16, temp=0)\n数据/指令隔离提示词；空上下文→“证据不足”", "green", "roundrect", 1.8, False, 11),

        # Evaluation boxes
        Box("audit_log", 1044, 120, 230, 108, "全链路审计日志\nraw.jsonl / detect_eval.jsonl\n逐文档记录完整性、来源、\n语义分数、缓存命中与分阶段耗时", "green", "cylinder", 1.6, False, 11),
        Box("metrics_box", 1044, 266, 230, 110, "自动化指标与图表重算\nsrc/metrics.py & analyze_results.py\nASR(被攻击/暴露)、正确率、\nP/R/F1/FPR、误伤与 P95 时延", "blue", "roundrect", 1.5, False, 11),
        Box("iso_inner", 1060, 456, 198, 142, "仅用于离线评分与审计：\n• label (benign/malicious)\n• attack_type (I1/I2/F1/F2)\n• payload & expected_terms\n严禁传入检测器与生成器", "red", "roundrect", 1.4, False, 10.8),
    ]

    edges = [
        Edge("e1", "a_corpus", "b_manifest", "计算基线哈希", "#4E79A7", False, 1.5, "bottom", "top"),
        Edge("e2", "b_manifest", "e_index", "构建语料索引", "#4E79A7", False, 1.5, "bottom", "top"),
        Edge("e3", "b_manifest", "g_integrity", "基线查验", "#59A14F", True, 1.5, "right", "left", [(340, 320), (340, 280)]),
        Edge("e4", "e_index", "ret_topk", "向量/TF-IDF 召回", "#4E79A7", True, 1.5, "right", "bottom", [(334, 461), (334, 210), (811, 210)]),
        Edge("e5", "q_in", "ret_topk", "编码检索", "#4E79A7", False, 1.6, "right", "left"),
        Edge("e6", "ret_topk", "g_integrity", "Top-5 候选", "#495057", False, 1.6, "bottom", "top", [(811, 204), (469, 204)]),
        Edge("e7", "g_integrity", "g_prov", "pass", "#F28E2B", False, 1.8, "right", "left"),
        Edge("e8", "g_prov", "g_sem", "allow", "#F28E2B", False, 1.8, "right", "left"),
        Edge("e9", "g_sem", "gate_dec", "风险评分", "#F28E2B", False, 1.8, "bottom", "top", [(882, 348), (675, 348)]),
        Edge("e10", "gate_dec", "block_box", "review / quarantine", "#E15759", False, 1.6, "right", "left"),
        Edge("e11", "gate_dec", "ctx_box", "allow 放行", "#59A14F", False, 1.8, "left", "top", [(516, 409)]),
        Edge("e12", "ctx_box", "gen_box", "受控上下文", "#59A14F", False, 1.8, "right", "left"),
        Edge("e13", "gen_box", "audit_log", "写入回答与审计", "#59A14F", False, 1.6, "right", "left", [(1012, 548), (1012, 174)]),
        Edge("e14", "audit_log", "metrics_box", "离线重算汇总", "#4E79A7", False, 1.6, "bottom", "top"),
        Edge("e15", "iso_inner", "metrics_box", "离线真值比对", "#CC3311", True, 1.6, "top", "bottom"),
    ]

    legend = [
        ("blue", "输入 / 检索 / 数据处理", False),
        ("orange", "核心防御模块（加粗）", False),
        ("yellow", "处置决策网关", False),
        ("green", "基线存储 / 放行 / 审计", False),
        ("red", "隔离拦截 / 评价真值", False),
        ("boundary", "评价隔离红线（防泄露）", True),
    ]
    return DiagramSpec(
        slug="fig1_system_architecture",
        title="图 1  RAG 知识库投毒检测与可信增强系统总体架构（模块 A–F）",
        subtitle="离线基线构建 → 在线三层顺序筛查（SHA-256 + 来源规则 + 本地 1.5B 双分支语义检测）→ 受控生成与隔离审计闭环",
        width=1320,
        height=700,
        boxes=boxes,
        edges=edges,
        legend_items=legend,
    )


def make_fig2_defense_flow() -> DiagramSpec:
    boxes = [
        Box("c_sem", 640, 290, 588, 340, "层 3：本地 LLM 双分支语义检测内部流程（PROMPT_VERSION = split-v6）", "gray", "container", 1.3, True, 11.5, True),

        Box("in_doc", 64, 92, 240, 66, "Top-5 检索候选文档 doc\n含 doc_id / text / source", "blue", "roundrect", 1.6, False, 12, True),

        Box("step1", 64, 198, 240, 68, "步骤 1：SHA-256 完整性校验\nverify(doc, manifest)", "orange", "roundrect", 2.2, False, 11.5),
        Box("d1", 104, 304, 160, 74, "哈希校验状态？", "yellow", "diamond", 1.7, False, 11.5, True),

        Box("step2", 64, 422, 240, 68, "步骤 2：来源规则评估\nprovenance.assess(doc, registry)", "orange", "roundrect", 2.2, False, 11.5),
        Box("d2", 104, 530, 160, 74, "来源是否可信\n且在白名单？", "yellow", "diamond", 1.7, False, 11.5, True),

        Box("q_fast", 370, 304, 210, 74, "直接隔离 / 复核\n• fail → quarantine\n• missing → review\n（跳过 LLM 节省算力）", "red", "roundrect", 1.6, False, 11),
        Box("r_prov", 370, 530, 210, 74, "转人工复核（review）\n• distro_wiki（已验证未列）\n• forum / blog / archive\n保守策略：不进上下文", "red", "roundrect", 1.6, False, 11),

        # Right side: Semantic detector
        Box("cache_d", 672, 336, 174, 72, "缓存命中？\n(prompt+text+ref)", "yellow", "diamond", 1.6, False, 11, True),
        Box("br1", 896, 326, 306, 82, "分支 1：行为指令短调用（≤32 tokens）\n输出 {\"label\": attack | unclear | quoted | none}\n分值：0.90 / 0.55 / 0.25 / 0.02（失败重试 1 次）", "orange", "roundrect", 2.0, False, 10.8),
        Box("br2", 896, 434, 306, 82, "分支 2：事实一致性短调用（≤32 tokens）\n输出 {\"label\": contradicted | insufficient | supported}\n分值：0.85 / 0.50 / 0.05（仅读 text + trusted_ref）", "orange", "roundrect", 2.0, False, 10.8),
        Box("agg", 672, 540, 530, 66, "冻结风险聚合：risk_score = max(score_injection, score_fact)\n解析修复后仍失败则回退 review；结果写入 detector_cache.jsonl", "teal", "roundrect", 1.6, False, 11.2),

        # Bottom decision & output
        Box("d3", 548, 660, 200, 76, "risk_score 阈值判定\n≥0.70 / ≥0.40 / <0.40", "yellow", "diamond", 1.8, False, 11.5, True),
        Box("out_block", 830, 666, 396, 66, "quarantine (≥0.70) 或 review (0.40–0.70)\n排除出生成上下文，写入审计日志（记入 FPR / 误伤统计）", "red", "roundrect", 1.6, False, 11),
        Box("out_allow", 64, 666, 396, 66, "allow (<0.40)：进入受控生成上下文\n按 [doc_id] text 拼接（≤3600 字符）；若全空→程序拒答“证据不足”", "green", "roundrect", 1.8, False, 11, True),
    ]

    edges = [
        Edge("e1", "in_doc", "step1", "", "#4E79A7", False, 1.6, "bottom", "top"),
        Edge("e2", "step1", "d1", "", "#F28E2B", False, 1.6, "bottom", "top"),
        Edge("e3", "d1", "q_fast", "fail / missing", "#E15759", False, 1.6, "right", "left"),
        Edge("e4", "d1", "step2", "integrity_pass", "#59A14F", False, 1.6, "bottom", "top", label_offset=(48, 0)),
        Edge("e5", "step2", "d2", "", "#F28E2B", False, 1.6, "bottom", "top"),
        Edge("e6", "d2", "r_prov", "未列 / 未知 / 伪冒", "#E15759", False, 1.6, "right", "left"),
        Edge("e7", "d2", "cache_d", "trusted allow", "#59A14F", False, 1.7, "bottom", "left", [(184, 624), (610, 624), (610, 372)], label_offset=(0, -10)),
        Edge("e8", "cache_d", "br1", "未命中", "#F28E2B", False, 1.6, "right", "left"),
        Edge("e9", "cache_d", "br2", "未命中", "#F28E2B", False, 1.6, "right", "left", [(868, 372), (868, 475)]),
        Edge("e10", "cache_d", "agg", "缓存命中（0s）", "#59A14F", True, 1.6, "bottom", "top", [(759, 540)], label_offset=(54, 0)),
        Edge("e11", "br1", "agg", "", "#F28E2B", False, 1.5, "right", "top", [(1216, 367), (1216, 526), (1050, 526)]),
        Edge("e12", "br2", "agg", "", "#F28E2B", False, 1.5, "bottom", "top", [(1049, 540)]),
        Edge("e13", "agg", "d3", "输出风险分", "#495057", False, 1.7, "bottom", "top", [(937, 642), (648, 642)]),
        Edge("e14", "d3", "out_block", "≥ 0.40 拦截", "#E15759", False, 1.7, "right", "left"),
        Edge("e15", "d3", "out_allow", "< 0.40 放行", "#59A14F", False, 1.8, "left", "right"),
    ]

    legend = [
        ("blue", "候选文档输入", False),
        ("orange", "核心校验 / 检测步骤", False),
        ("yellow", "条件分支与阈值判断", False),
        ("teal", "风险聚合与缓存机制", False),
        ("green", "放行进入受控上下文", False),
        ("red", "隔离 / 复核排除", False),
    ]
    return DiagramSpec(
        slug="fig2_defense_decision_flow",
        title="图 2  组合防护（Combined）与双分支语义检测决策流程图",
        subtitle="顺序拦截（哈希 → 来源 → 本地 1.5B 双分支短 JSON 检测）与冻结阈值决策规则",
        width=1280,
        height=790,
        boxes=boxes,
        edges=edges,
        legend_items=legend,
    )


def make_fig3_threat_model() -> DiagramSpec:
    boxes = [
        Box("c_atk", 28, 80, 346, 528, "攻击者能力边界与投毒载荷", "gray", "container", 1.2, True, 12, True),
        Box("c_post", 404, 80, 848, 250, "场景 A：post_ingestion（入库建基线后发生篡改）", "green", "container", 1.4, True, 12, True),
        Box("c_pre", 404, 358, 848, 250, "场景 B：pre_ingestion（投毒发生在基线建立之前）", "red", "container", 1.4, True, 12, True),

        # Attacker column
        Box("atk_cap", 48, 124, 306, 114, "攻击假设（恒定语料规模 400）\n• 替换同 doc_id 正常文档（5%/10%/20%）\n• 可伪造声明式 source（如 man_pages）\n• 不可篡改已落盘基线清单与评价真值", "red", "roundrect", 1.7, False, 11, align="left"),
        Box("atk_inj", 48, 266, 306, 110, "载荷类型 1：提示注入（100 条）\n• I1 定向改写答案指令\n• I2 诱导输出哨兵 RAG_POISON_999\n伪装为技术备注或系统提示", "orange", "roundrect", 1.8, False, 11, align="left"),
        Box("atk_fact", 48, 404, 306, 110, "载荷类型 2：错误技术事实（100 条）\n• F1 / F2 颠倒 Linux 系统调用语义\n（如 fork 返回值、SIGKILL 可捕获等）\n无显式攻击指令，规则词难以拦截", "orange", "roundrect", 1.8, False, 11, align="left"),
        Box("atk_iso", 48, 534, 306, 56, "安全边界：攻击者无法触达 evaluation_only", "boundary", "roundrect", 1.8, True, 11, True),

        # Post-ingestion lane
        Box("p1", 426, 134, 168, 82, "1. 干净语料入库\n400 条正常文档", "blue", "roundrect", 1.5, False, 11.5),
        Box("p2", 626, 134, 178, 82, "2. 先建 SHA-256 基线\n记录干净文本摘要", "green", "cylinder", 1.6, False, 11.5),
        Box("p3", 836, 134, 178, 82, "3. 攻击者替换文档\n文本字节改变\n（同 doc_id 替换）", "red", "roundrect", 1.7, False, 11.5),
        Box("p4", 1046, 124, 184, 104, "4. 完整性校验结果\n100% 检出篡改\n16/16 · 28/28 · 55/55\nASR = 0（无需语义层）", "green", "roundrect", 2.0, False, 11, True),
        Box("p_note", 426, 244, 804, 62, "关键结论（post_ingestion）：哈希校验对“入库后字节级篡改”零漏报、低开销；20% 投毒下 integrity 组正确率 83.3%（vs baseline 37.5%）。", "teal", "roundrect", 1.2, False, 11),

        # Pre-ingestion lane
        Box("r1", 426, 412, 168, 82, "1. 投毒文档混入\n同 doc_id 替换\n（含伪造 man_pages）", "red", "roundrect", 1.7, False, 11.2),
        Box("r2", 626, 412, 178, 82, "2. 后建 SHA-256 基线\n基线已包含投毒文本\n哈希校验检出率 0%", "yellow", "cylinder", 1.7, False, 11.2),
        Box("r3", 836, 412, 178, 82, "3. 来源 + 语义联防\n来源拦截 31/55 未知源\n语义拦截 24/55 伪造源", "orange", "roundrect", 2.2, False, 11.2),
        Box("r4", 1046, 402, 184, 104, "4. 防护结果与代价\nASR(被攻击) 65% → 0%\n代价：14 条正常\ndistro_wiki 被转复核", "green", "roundrect", 1.8, False, 11, True),
        Box("r_note", 426, 522, 804, 62, "关键结论（pre_ingestion）：SHA-256 无法发现入库前投毒（integrity 组与 baseline 完全一致，ASR 65%）；必须依赖来源与内容级语义检测互补。", "boundary", "roundrect", 1.4, True, 11),
    ]

    edges = [
        Edge("e1", "p1", "p2", "", "#4E79A7", False, 1.6, "right", "left"),
        Edge("e2", "p2", "p3", "入库后篡改", "#E15759", False, 1.6, "right", "left"),
        Edge("e3", "p3", "p4", "SHA-256 失败", "#59A14F", False, 1.8, "right", "left"),
        Edge("e4", "r1", "r2", "", "#E15759", False, 1.6, "right", "left"),
        Edge("e5", "r2", "r3", "哈希全部放行", "#D4A017", False, 1.6, "right", "left"),
        Edge("e6", "r3", "r4", "全部隔离", "#59A14F", False, 1.8, "right", "left"),
        Edge("e7", "atk_inj", "p3", "注入载荷", "#E15759", True, 1.4, "right", "top", [(388, 321), (388, 108), (925, 108)]),
        Edge("e8", "atk_fact", "r1", "投毒入库", "#E15759", True, 1.5, "right", "left", [(388, 459), (388, 453)]),
    ]

    legend = [
        ("blue", "正常语料状态", False),
        ("red", "攻击 / 投毒篡改", False),
        ("yellow", "基线失效状态（pre）", False),
        ("orange", "载荷与核心防御层", False),
        ("green", "成功检出与阻断", False),
        ("boundary", "核心安全边界提示", True),
    ]
    return DiagramSpec(
        slug="fig3_threat_model_scenes",
        title="图 3  威胁模型与入库前后（Pre vs Post Ingestion）投毒对照流程图",
        subtitle="受控对照实验设计：区分字节级篡改（post）与供应链入库前污染（pre）对三层防护的不同可观测性",
        width=1280,
        height=670,
        boxes=boxes,
        edges=edges,
        legend_items=legend,
    )


def make_fig4_evolution() -> DiagramSpec:
    boxes = [
        Box("s1", 36, 98, 286, 174, "阶段 1：正式轮四组对照（10/27）\n768 查询 + 1200 文档全语料评价\n• 组合防护 ASR 65% → 0%\n• 检测器 P=0.976 / R=1.000 / FPR=0.63%\n• 暴露问题：组合组 20% 投毒正确率\n  降至 66.7%（14 条 distro_wiki 误伤）", "blue", "roundrect", 1.7, False, 11, align="left"),
        Box("s2", 364, 98, 286, 174, "阶段 2：证据粒度四条件消融（10/29）\n97 开发题 × 4 条件 = 388 条推理\n• 句子不滤 42 / 句子过滤 47\n• 段落不滤 67 / 段落过滤 72\n  （原 AI 暂判口径）\n• 结论：完整段落显著优于断句抽取", "orange", "roundrect", 2.0, False, 11, align="left"),
        Box("s3", 692, 98, 286, 174, "阶段 3：API 挑战与 GPT-6 复核（10/29–30）\n8 事实簇 × 7 场景 = 56 题 × 4 = 224 条\n• GPT-6 联合口径：段落不滤 27/56\n  > 段落过滤 22/56\n• 明确失败：全文禁止词过滤误伤\n  8/8 合法引用攻击样例的正确文档", "orange", "roundrect", 2.0, False, 11, align="left"),
        Box("s4", 1020, 98, 264, 174, "阶段 4：语义门控 v1（10/30）\n【负面实验 · 诚实止损】\n153 记录（133 次额外调用）\n• 133/133 全部被拒（覆盖率 0%）\n• 24 次正负/编码/解码诊断确认\n  不可仅归因于约束解码 → 不并入默认", "red", "roundrect", 2.2, False, 11, align="left"),

        # Bottom row: Stage 5 + Review + Freeze
        Box("s5", 36, 344, 412, 198, "阶段 5：BGE-reranker-v2-m3 重排与句界标记（10/30）\n• 阶段 5a（40 对相关性校准）：局部阈值 1.275 通过 8/8 正例与 4/4 无关负例，\n  但仅复述问题（8/8，分值 10.65–10.82）与错误事实（6/8）同样高分通过\n  → 禁止把相关性阈值当证据充分性或事实可靠门槛\n• 阶段 5b（153 题 × 4 组 = 612 条生成）：完成基线 / 重排 / 标记 / 重排+标记实测", "orange", "roundrect", 2.0, False, 11, align="left"),
        Box("s6", 494, 344, 388, 198, "阶段 5c：44 项补充复核与哈希核验\n• 逐项核对 Linux man-pages 与内核文档，回填 73 条新回答，\n  612 条记录全部有状态（verify_rerank_review.py 通过）\n• 混合核心口径（两集分开，不混算总准确率）：\n  - 开发 97 题：基线 67 / 重排 66 / 标记 65 / 重排+标记 66\n  - API 56 题：基线 27 / 重排 29 / 标记 25 / 重排+标记 32", "teal", "roundrect", 1.7, False, 11, align="left"),
        Box("s7", 928, 344, 356, 198, "最终工程决策与开源发布冻结\n• 默认方案：保留完整段落证据 + 三层可审计流水线\n• 优先候选：重排+标记（API +5 且 0 回归，待做顺序/裁剪消融）\n• 显式排除：全局禁止词过滤、语义门控 v1、相关性硬拒答\n• 复现保障：64 项单元测试通过 + SHA-256 哈希核验\n• 后续扩展：冻结方法后新建 ≥24 个未见事实簇评测", "green", "roundrect", 2.0, False, 11, align="left"),

        Box("note_bar", 36, 568, 1248, 52, "方法论原则：严格分口径报告（规则评分 / 原 AI 暂判 / GPT-6 事后联合口径 / 模型辅助溯源补评），已暴露数据仅作开发诊断，不宣称未见数据泛化。", "boundary", "roundrect", 1.5, True, 11.2, True),
    ]

    edges = [
        Edge("e1", "s1", "s2", "诊断覆盖率下降", "#4E79A7", False, 1.7, "right", "left"),
        Edge("e2", "s2", "s3", "压力测试验证", "#F28E2B", False, 1.7, "right", "left"),
        Edge("e3", "s3", "s4", "尝试小模型自审", "#E15759", False, 1.7, "right", "left"),
        Edge("e4", "s4", "s5", "止损转向专用重排", "#E15759", True, 1.8, "bottom", "top", [(1152, 308), (242, 308)], label_offset=(0, -10)),
        Edge("e5", "s5", "s6", "补齐 73 条新回答状态", "#F28E2B", False, 1.7, "right", "left"),
        Edge("e6", "s6", "s7", "哈希核验与方案冻结", "#59A14F", False, 1.8, "right", "left"),
    ]

    legend = [
        ("blue", "基线与正式轮实验", False),
        ("orange", "核心消融与迭代优化", False),
        ("red", "负面实验与失败止损", False),
        ("teal", "溯源补评与哈希核验", False),
        ("green", "冻结交付决策", False),
        ("boundary", "评测口径与数据边界原则", True),
    ]
    return DiagramSpec(
        slug="fig4_experiment_evolution_flow",
        title="图 4  五阶段实验演进、负面诊断与工程冻结闭环流程图",
        subtitle="以失败驱动迭代：从正式轮（768 条）到段落消融（388 条）、API 挑战（224 条）、语义门控失败（153 条）与 BGE 重排消融（612 条）",
        width=1320,
        height=680,
        boxes=boxes,
        edges=edges,
        legend_items=legend,
    )


def validate_no_foreground_overlap(spec: DiagramSpec) -> None:
    fg = [b for b in spec.boxes if b.shape != "container"]
    for i in range(len(fg)):
        for j in range(i + 1, len(fg)):
            a, b = fg[i], fg[j]
            overlap_x = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
            overlap_y = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
            if overlap_x > 0 and overlap_y > 0:
                raise AssertionError(f"[{spec.slug}] Box overlap between {a.id} and {b.id}: {overlap_x}x{overlap_y}")


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
        # Verify XML is strictly well-formed
        ET.fromstring(drawio_xml)
        drawio_path = OUT_DIR / f"{spec.slug}.drawio"
        drawio_path.write_text(drawio_xml, encoding="utf-8")

        svg_xml = build_svg(spec)
        ET.fromstring(svg_xml)
        svg_path = OUT_DIR / f"{spec.slug}.svg"
        svg_path.write_text(svg_xml, encoding="utf-8")
        print(f"Generated: {drawio_path.relative_to(ROOT)} & {svg_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
