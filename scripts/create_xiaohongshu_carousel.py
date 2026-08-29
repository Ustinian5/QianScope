from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "xiaohongshu"
RAW = ROOT / "output" / "playwright"
SOURCE = OUT / "source"

W, H = 1080, 1440

PAPER = (247, 244, 237, 255)
PAPER_2 = (252, 250, 245, 255)
INK = (28, 32, 36, 255)
MUTED = (102, 108, 112, 255)
LINE = (219, 214, 203, 255)
BLUE = (47, 88, 229, 255)
BLUE_SOFT = (235, 239, 253, 255)
CORAL = (244, 99, 78, 255)
CORAL_SOFT = (255, 237, 231, 255)
JADE = (93, 137, 122, 255)
JADE_SOFT = (232, 241, 237, 255)
WHITE = (255, 255, 255, 255)

FONT_SANS = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
FONT_SERIF = Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf")
FONT_SANS_FALLBACK = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_SERIF_FALLBACK = Path(r"C:\Windows\Fonts\simsun.ttc")


def font(size: int, *, serif: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_SERIF if serif else FONT_SANS
    if not path.exists():
        path = FONT_SERIF_FALLBACK if serif else FONT_SANS_FALLBACK
    return ImageFont.truetype(str(path), size=size)


def canvas(color: tuple[int, int, int, int] = PAPER) -> Image.Image:
    return Image.new("RGBA", (W, H), color)


def add_paper_texture(im: Image.Image, strength: int = 6) -> None:
    texture = Image.effect_noise((W, H), 18).convert("L")
    texture = ImageOps.autocontrast(texture).point(lambda p: 128 + (p - 128) * 0.15)
    tint = Image.new("RGBA", (W, H), (116, 102, 78, strength))
    tint.putalpha(texture.point(lambda p: max(0, min(strength, abs(p - 128) // 8))))
    im.alpha_composite(tint)


def draw_mark(im: Image.Image, x: int, y: int, width: int = 76) -> None:
    mark_path = ROOT / "artifacts" / "brand" / "gravity-echo" / "company-mark-ink.png"
    mark = Image.open(mark_path).convert("RGBA")
    ratio = width / mark.width
    mark = mark.resize((width, int(mark.height * ratio)), Image.Resampling.LANCZOS)
    im.alpha_composite(mark, (x, y))


def header(im: Image.Image, page: int, label: str) -> None:
    d = ImageDraw.Draw(im)
    draw_mark(im, 58, 42, 70)
    d.text((144, 43), "黔镜", font=font(28, serif=True), fill=INK)
    d.text((145, 78), "QIANSCOPE · SOCIAL WORLD", font=font(13), fill=MUTED)
    label_text = f"{label}  ·  {page:02d}/08"
    box = d.textbbox((0, 0), label_text, font=font(15))
    d.text((W - 58 - (box[2] - box[0]), 59), label_text, font=font(15), fill=BLUE)
    d.line((58, 118, W - 58, 118), fill=LINE, width=1)


def footer(im: Image.Image, page: int, note: str | None = None) -> None:
    d = ImageDraw.Draw(im)
    d.line((58, 1370, W - 58, 1370), fill=LINE, width=1)
    d.text((58, 1385), note or "合成人格与推演结果用于研究辅助，不代表现实个人，也不替代真实调查。", font=font(15), fill=MUTED)
    n = f"{page:02d}"
    box = d.textbbox((0, 0), n, font=font(18))
    d.text((W - 58 - (box[2] - box[0]), 1382), n, font=font(18), fill=CORAL)


def rounded_panel(
    im: Image.Image,
    box: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int, int] = WHITE,
    radius: int = 28,
    outline: tuple[int, int, int, int] | None = LINE,
    shadow: bool = True,
) -> None:
    x0, y0, x1, y1 = box
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle((x0 + 6, y0 + 12, x1 + 6, y1 + 12), radius=radius, fill=(43, 40, 34, 42))
        sh = sh.filter(ImageFilter.GaussianBlur(18))
        im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 0)


def screenshot_panel(
    im: Image.Image,
    source: Path,
    box: tuple[int, int, int, int],
    *,
    radius: int = 28,
    align: tuple[float, float] = (0.5, 0.5),
    border: tuple[int, int, int, int] = LINE,
) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    rounded_panel(im, box, fill=WHITE, radius=radius, outline=None, shadow=True)
    shot = Image.open(source).convert("RGBA")
    shot = ImageOps.fit(shot, (w, h), method=Image.Resampling.LANCZOS, centering=align)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    im.paste(shot, (x0, y0), mask)
    ImageDraw.Draw(im).rounded_rectangle(box, radius=radius, outline=border, width=2)


def wrap_text(text: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            trial = current + char
            if current and f.getlength(trial) > max_width:
                lines.append(current)
                current = char
            else:
                current = trial
        if current:
            lines.append(current)
    return lines


def paragraph(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    size: int = 28,
    width: int = 900,
    fill: tuple[int, int, int, int] = MUTED,
    leading: float = 1.55,
    serif: bool = False,
) -> int:
    f = font(size, serif=serif)
    x, y = xy
    step = int(size * leading)
    for line in wrap_text(text, f, width):
        d.text((x, y), line, font=f, fill=fill)
        y += step
    return y


def pill(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    fill: tuple[int, int, int, int] = BLUE_SOFT,
    color: tuple[int, int, int, int] = BLUE,
    size: int = 20,
    pad_x: int = 20,
    pad_y: int = 11,
) -> tuple[int, int, int, int]:
    f = font(size)
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0] + pad_x * 2
    h = bbox[3] - bbox[1] + pad_y * 2
    x, y = xy
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=fill)
    d.text((x + pad_x, y + pad_y - bbox[1]), text, font=f, fill=color)
    return x, y, x + w, y + h


def title(d: ImageDraw.ImageDraw, y: int, lines: list[tuple[str, tuple[int, int, int, int]]], size: int = 64) -> int:
    f = font(size, serif=True)
    for text, color in lines:
        d.text((58, y), text, font=f, fill=color)
        y += int(size * 1.28)
    return y


def save(im: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(OUT / name, quality=96, optimize=True)


def card_01() -> None:
    bg = Image.open(SOURCE / "cover-background.png").convert("RGBA")
    bg = ImageOps.fit(bg, (W, H), method=Image.Resampling.LANCZOS)

    # Calm the headline area while keeping the generated paper texture visible.
    veil = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    v = ImageDraw.Draw(veil)
    for y in range(0, 760):
        alpha = int(128 * (1 - y / 760)) + 18
        v.line((0, y, W, y), fill=(252, 250, 245, alpha))
    bg.alpha_composite(veil)
    d = ImageDraw.Draw(bg)

    draw_mark(bg, 60, 55, 78)
    d.text((151, 56), "黔镜 QianScope", font=font(27, serif=True), fill=INK)
    d.text((153, 91), "GUIYANG SOCIAL WORLD", font=font(14), fill=BLUE)
    pill(d, (784, 57), "项目首次公开", fill=CORAL_SOFT, color=CORAL, size=18)

    d.text((58, 188), "我们把一座城市", font=font(77, serif=True), fill=INK)
    d.text((58, 296), "装进了「可推演」", font=font(77, serif=True), fill=BLUE)
    d.text((58, 404), "的社会世界", font=font(77, serif=True), fill=INK)
    paragraph(
        d,
        (62, 538),
        "5,000 个稳定人格 Agent，在地点、关系与信息渠道中独立判断、行动与记忆。",
        size=27,
        width=830,
        fill=(66, 72, 74, 255),
        leading=1.5,
    )
    pill(d, (62, 661), "黔镜 QianScope · 通用社会事件预测", fill=(255, 255, 255, 222), color=INK, size=20)

    rounded_panel(bg, (58, 1272, 1022, 1378), fill=(250, 248, 242, 232), radius=28, outline=(255, 255, 255, 150), shadow=True)
    d.text((88, 1291), "不是预言", font=font(24, serif=True), fill=CORAL)
    d.text((223, 1291), "·", font=font(24), fill=MUTED)
    d.text((258, 1291), "是带边界、可复现的条件模拟", font=font(24, serif=True), fill=INK)
    d.text((89, 1334), "PROJECT NOTE 01  /  小红书图文版", font=font(14), fill=MUTED)
    save(bg, "01-cover.png")


def card_02() -> None:
    im = canvas()
    add_paper_texture(im)
    header(im, 2, "WHAT IS QIANSCOPE")
    d = ImageDraw.Draw(im)
    title(d, 156, [("先别急着问“准不准”", INK), ("先进入这个世界。", BLUE)], size=62)
    paragraph(d, (58, 330), "黔镜把贵阳做成可探索的社会世界：从城市全景进入地点，再观察人群、关系与事件如何流动。", size=25, width=900)
    screenshot_panel(im, RAW / "home-world.png", (58, 438, 1022, 1107), radius=30)

    stats = [
        ("5,000", "稳定人格原型", BLUE, BLUE_SOFT),
        ("666.89 万", "加权代表尺度", CORAL, CORAL_SOFT),
        ("7 + 28", "主地点 · 独立场景", JADE, JADE_SOFT),
    ]
    x = 58
    for value, label, color, fill in stats:
        rounded_panel(im, (x, 1142, x + 298, 1305), fill=fill, radius=24, outline=None, shadow=False)
        d.text((x + 24, 1165), value, font=font(40, serif=True), fill=color)
        d.text((x + 24, 1233), label, font=font(20), fill=INK)
        x += 333
    footer(im, 2)
    save(im, "02-social-world.png")


def card_03() -> None:
    im = canvas(PAPER_2)
    add_paper_texture(im)
    header(im, 3, "IMAGE IS THE UI")
    d = ImageDraw.Draw(im)
    title(d, 156, [("地图不是背景", INK), ("它就是交互入口。", CORAL)], size=64)
    paragraph(d, (58, 334), "点击会展、科创城、校园、古镇或社区，画面会继续下钻到建筑与室内；人物就生活在这些地点里。", size=25, width=900)
    screenshot_panel(im, RAW / "openflipbook-location.png", (58, 438, 1022, 1107), radius=30)

    labels = [("城市全景", BLUE_SOFT, BLUE), ("地点画页", CORAL_SOFT, CORAL), ("室内场景", JADE_SOFT, JADE), ("人物状态", (240, 236, 248, 255), (106, 76, 145, 255))]
    x = 58
    for idx, (text, fill, color) in enumerate(labels):
        _, _, x1, _ = pill(d, (x, 1142), text, fill=fill, color=color, size=21, pad_x=24, pad_y=13)
        x = x1 + 16
        if idx < len(labels) - 1:
            d.text((x - 8, 1153), "→", font=font(20), fill=MUTED)
            x += 30
    paragraph(d, (58, 1228), "OpenFlipbook 的“图像即界面”让世界不再是一张仪表盘，而是可以被进入、搜索和访谈的社会现场。", size=23, width=930, fill=INK)
    footer(im, 3)
    save(im, "03-world-drilldown.png")


def card_04() -> None:
    im = canvas()
    add_paper_texture(im)
    header(im, 4, "STABLE PERSONA")
    d = ImageDraw.Draw(im)
    title(d, 156, [("他们不是 5,000 个", INK), ("随机生成的 Prompt。", BLUE)], size=61)
    paragraph(d, (58, 330), "每个 Agent 都有稳定身份、人格向量、动态状态、三层记忆与社会关系；事件能改变状态，但不会随意改写人格。", size=25, width=910)
    screenshot_panel(im, RAW / "persona-panel.png", (58, 438, 1022, 1107), radius=30, align=(0.52, 0.5))

    items = [
        ("54", "公开人格维度"),
        ("3 层", "工作 / 事件 / 长期记忆"),
        ("5+", "关系与传播类型"),
        ("稳定", "ID · 来源 · profile hash"),
    ]
    x_positions = [58, 300, 542, 784]
    for x, (value, label) in zip(x_positions, items):
        rounded_panel(im, (x, 1142, x + 222, 1306), fill=WHITE, radius=22, outline=LINE, shadow=False)
        d.text((x + 20, 1162), value, font=font(35, serif=True), fill=CORAL if x in (300, 784) else BLUE)
        paragraph(d, (x + 20, 1216), label, size=17, width=182, fill=INK, leading=1.35)
    footer(im, 4)
    save(im, "04-stable-persona.png")


def card_05() -> None:
    im = canvas(PAPER_2)
    add_paper_texture(im)
    header(im, 5, "MULTI-AGENT RUNTIME")
    d = ImageDraw.Draw(im)
    title(d, 156, [("真正的技术高度", INK), ("在“每个 Agent 都参与”。", CORAL)], size=59)
    paragraph(d, (58, 330), "不是抽几个角色代表全体：三级 Agent 都执行同一套观察—判断—行动—记忆循环，只是推理深度不同。", size=24, width=915)

    tiers = [
        ("50", "关键 Agent", "高影响 · 高不确定性 · 深度策略", CORAL, CORAL_SOFT),
        ("450", "代表 Agent", "覆盖主要群体 · 受约束策略", BLUE, BLUE_SOFT),
        ("4,500", "背景 Agent", "向量化运行 · 保留规模与尾部", JADE, JADE_SOFT),
    ]
    y = 445
    for count, name, detail, color, fill in tiers:
        rounded_panel(im, (58, y, 1022, y + 122), fill=fill, radius=24, outline=None, shadow=False)
        d.text((84, y + 27), count, font=font(43, serif=True), fill=color)
        d.text((248, y + 23), name, font=font(29, serif=True), fill=INK)
        d.text((248, y + 68), detail, font=font(20), fill=MUTED)
        pill(d, (822, y + 34), "实际执行", fill=(255, 255, 255, 190), color=color, size=18)
        y += 140

    d.text((58, 890), "每一轮都发生什么？", font=font(28, serif=True), fill=INK)
    loop = [("观察", "接触不同信息"), ("判断", "基于人格与记忆"), ("行动", "分享 / 讨论 / 参与"), ("记忆", "更新状态与关系")]
    x = 58
    for idx, (name, detail) in enumerate(loop):
        rounded_panel(im, (x, 946, x + 214, 1082), fill=WHITE, radius=22, outline=LINE, shadow=False)
        d.ellipse((x + 18, 964, x + 52, 998), fill=BLUE if idx % 2 == 0 else CORAL)
        d.text((x + 68, 958), name, font=font(27, serif=True), fill=INK)
        d.text((x + 20, 1021), detail, font=font(16), fill=MUTED)
        if idx < len(loop) - 1:
            d.text((x + 222, 987), "→", font=font(28), fill=MUTED)
        x += 244

    rounded_panel(im, (58, 1120, 1022, 1308), fill=(32, 38, 48, 255), radius=26, outline=None, shadow=True)
    d.text((84, 1146), "关系传播", font=font(24, serif=True), fill=(139, 182, 168, 255))
    d.text((84, 1191), "家庭 · 熟人 · 同事 · 社区 · 线上", font=font(23), fill=WHITE)
    d.line((520, 1145, 520, 1280), fill=(90, 98, 110, 255), width=2)
    d.text((550, 1146), "多路径反事实", font=font(24, serif=True), fill=(117, 151, 255, 255))
    paragraph(d, (550, 1191), "基线 / 描述情景 / 替代情景\n共享随机路径，输出差值与区间", size=20, width=420, fill=WHITE, leading=1.45)
    footer(im, 5)
    save(im, "05-agent-runtime.png")


def card_06() -> None:
    im = canvas()
    add_paper_texture(im)
    header(im, 6, "12 PRODUCT TOOLS")
    d = ImageDraw.Draw(im)
    title(d, 156, [("不止预测一个事件", INK), ("还可以提前做 12 类测试。", BLUE)], size=58)
    paragraph(d, (58, 330), "同一个社会世界底座，承载问卷、事件、营销、品牌、产品、定价、竞品、转化、流失与传播节点等工具。", size=24, width=920)
    screenshot_panel(im, RAW / "toolkit.png", (58, 438, 1022, 1107), radius=30, align=(0.58, 0.5))

    left = ["问卷 / 事件", "营销 / 趋势", "品牌 / 产品"]
    right = ["需求 / 定价", "竞品 / 漏斗", "流失 / 达人"]
    for col, items in enumerate((left, right)):
        x = 58 + col * 500
        for idx, text in enumerate(items):
            y = 1142 + idx * 54
            d.ellipse((x, y + 8, x + 18, y + 26), fill=CORAL if col else BLUE)
            d.text((x + 31, y), text, font=font(21), fill=INK)
    rounded_panel(im, (740, 1150, 1022, 1308), fill=CORAL_SOFT, radius=24, outline=None, shadow=False)
    d.text((770, 1171), "一个底座", font=font(24, serif=True), fill=CORAL)
    d.text((770, 1214), "多种业务问题", font=font(30, serif=True), fill=INK)
    d.text((770, 1261), "统一任务与报告", font=font(18), fill=MUTED)
    footer(im, 6)
    save(im, "06-toolkit.png")


def card_07() -> None:
    im = canvas(PAPER_2)
    add_paper_texture(im)
    header(im, 7, "PROBABILISTIC REPORT")
    d = ImageDraw.Draw(im)
    title(d, 156, [("我们给的不是一句", INK), ("“大概率会发生”。", CORAL)], size=61)
    paragraph(d, (58, 330), "结果从一句话结论开始，但会一路展开到问卷前后、群体差异、反事实情景、传播轨迹与限制边界。", size=24, width=920)
    screenshot_panel(im, RAW / "report-summary.png", (58, 438, 1022, 1069), radius=28, align=(0.5, 0.32))

    features = [
        ("前 / 后", "问卷分布", BLUE, BLUE_SOFT),
        ("P10·P50·P90", "路径区间", CORAL, CORAL_SOFT),
        ("A / B / C", "反事实对照", JADE, JADE_SOFT),
        ("REPLAY", "回放与导出", (105, 78, 151, 255), (241, 236, 248, 255)),
    ]
    x = 58
    for top, bottom, color, fill in features:
        rounded_panel(im, (x, 1110, x + 222, 1298), fill=fill, radius=22, outline=None, shadow=False)
        d.text((x + 20, 1136), top, font=font(25, serif=True), fill=color)
        d.text((x + 20, 1201), bottom, font=font(22), fill=INK)
        x += 242
    footer(im, 7)
    save(im, "07-report.png")


def card_08() -> None:
    im = canvas()
    add_paper_texture(im)
    header(im, 8, "ENGINEERING & TRUST")
    d = ImageDraw.Draw(im)
    title(d, 156, [("会模拟", INK), ("更要能复现。", BLUE)], size=67)
    paragraph(d, (58, 330), "技术栈不是堆名词，而是让每一次运行都能被校验、被重放、被质疑。", size=25, width=900)

    layers = [
        ("01  体验层", "Next.js 16 · React 19 · 高德 / MapLibre · OpenFlipbook", BLUE, BLUE_SOFT),
        ("02  API 层", "FastAPI · Pydantic · 同源网关 · 强类型数据契约", CORAL, CORAL_SOFT),
        ("03  模型层", "NumPy · scikit-learn · 多 Agent 数值运行时", JADE, JADE_SOFT),
        ("04  产物层", "Parquet · JSONL · SHA-256 · 确定性回放", (105, 78, 151, 255), (241, 236, 248, 255)),
    ]
    y = 432
    for name, detail, color, fill in layers:
        rounded_panel(im, (58, y, 1022, y + 122), fill=fill, radius=24, outline=None, shadow=False)
        d.text((84, y + 24), name, font=font(24, serif=True), fill=color)
        d.text((310, y + 28), detail, font=font(21), fill=INK)
        y += 142

    chips = ["固定随机种子", "未来信息隔离", "共享随机路径", "产物哈希校验"]
    x, y = 58, 1017
    for text in chips:
        _, _, x1, _ = pill(d, (x, y), text, fill=WHITE, color=INK, size=19, pad_x=19, pad_y=12)
        x = x1 + 14

    rounded_panel(im, (58, 1105, 1022, 1312), fill=(31, 37, 47, 255), radius=30, outline=None, shadow=True)
    d.text((87, 1133), "如果你也想提前看见“一群人会怎么反应”", font=font(29, serif=True), fill=WHITE)
    d.text((87, 1192), "欢迎来体验黔镜 QianScope", font=font(25), fill=(132, 164, 255, 255))
    d.text((87, 1242), "qianscope.zeabur.app", font=font(22), fill=(255, 159, 139, 255))
    d.text((624, 1242), "GitHub · Ustinian5/QianScope", font=font(18), fill=(205, 209, 216, 255))
    footer(im, 8, note="当前版本为开源研究实验系统；概率模拟不构成现实结果保证。")
    save(im, "08-engineering-cta.png")


def main() -> None:
    required = [
        SOURCE / "cover-background.png",
        RAW / "home-world.png",
        RAW / "openflipbook-location.png",
        RAW / "persona-panel.png",
        RAW / "toolkit.png",
        RAW / "report-summary.png",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing source assets:\n" + "\n".join(missing))

    for fn in (card_01, card_02, card_03, card_04, card_05, card_06, card_07, card_08):
        fn()
    print(f"Created 8 carousel images in {OUT}")


if __name__ == "__main__":
    main()
