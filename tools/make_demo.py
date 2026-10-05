"""Compose the Overrule demo video from dApp screenshots.

Slides are drawn with PIL and encoded with OpenCV (the bundled ffmpeg in this
environment has no PNG decoder, so cv2.VideoWriter is used instead).
"""

import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2

SHOTS = r"C:\Users\25372\AppData\Local\Temp\trae\screenshots"
OUT = r"C:\Users\25372\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6ac00e8ec083f3e781ae6dba\genlayer-overrule\docs\overrule-demo.mp4"

W, H = 1280, 720
FPS = 30
HOLD = 5.0
FADE = 0.6

BG = (13, 15, 22)
PANEL = (20, 23, 33)
ACCENT = (124, 92, 255)
GREEN = (74, 222, 128)
TEXT = (232, 234, 242)
MUTED = (150, 156, 176)
BORDER = (38, 42, 58)

FONTS = r"C:\Windows\Fonts"


def font(name, size):
    for candidate in (name, "segoeui.ttf", "arial.ttf"):
        path = os.path.join(FONTS, candidate)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def base_canvas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(0, H, 4):
        shade = int(6 * (y / H))
        d.line([(0, y), (W, y)], fill=(BG[0] + shade, BG[1] + shade, BG[2] + shade + 2))
    d.ellipse([-260, -320, 460, 260], fill=(24, 20, 46))
    d.ellipse([W - 380, H - 300, W + 260, H + 260], fill=(16, 26, 30))
    return img


def wrap(draw, text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def title_card():
    img = base_canvas()
    d = ImageDraw.Draw(img)
    f_big = font("seguisb.ttf", 104)
    f_tag = font("segoeui.ttf", 30)
    f_sub = font("segoeui.ttf", 22)

    d.text((W // 2, 250), "Overrule", font=f_big, fill=TEXT, anchor="mm")
    d.text((W // 2, 336), "An on-chain appeal court for content-moderation decisions",
           font=f_tag, fill=MUTED, anchor="mm")
    d.line([(W // 2 - 90, 388), (W // 2 + 90, 388)], fill=ACCENT, width=4)
    d.text((W // 2, 440), "GenLayer Intelligent Contract  ·  studionet", font=f_sub,
           fill=GREEN, anchor="mm")
    d.text((W // 2, 490), "The model classifies. The contract decides.", font=f_sub,
           fill=MUTED, anchor="mm")
    return img


def shot_card(step, title, subtitle, shot):
    img = base_canvas()
    d = ImageDraw.Draw(img)

    f_step = font("seguisb.ttf", 20)
    f_title = font("seguisb.ttf", 38)
    f_sub = font("segoeui.ttf", 21)

    d.rounded_rectangle([70, 44, 70 + 58, 44 + 34], radius=17, fill=ACCENT)
    d.text((70 + 29, 44 + 17), f"0{step}", font=f_step, fill=(255, 255, 255), anchor="mm")
    d.text((148, 50), title, font=f_title, fill=TEXT, anchor="lm")

    for i, line in enumerate(wrap(d, subtitle, f_sub, W - 160)[:2]):
        d.text((72, 104 + i * 30), line, font=f_sub, fill=MUTED)

    src = Image.open(os.path.join(SHOTS, shot)).convert("RGB")
    max_w, max_h = 620, 470
    scale = min(max_w / src.width, max_h / src.height)
    src = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)

    px, py = 70, 180
    d.rounded_rectangle([px - 2, py - 2, px + src.width + 2, py + src.height + 2],
                        radius=12, outline=BORDER, width=2)
    img.paste(src, (px, py))

    tx = px + src.width + 46
    tw = W - tx - 70
    f_h = font("seguisb.ttf", 24)
    f_b = font("segoeui.ttf", 22)

    bullets = BULLETS[step]
    y = 200
    for head, body in bullets:
        d.ellipse([tx, y + 8, tx + 9, y + 17], fill=GREEN)
        d.text((tx + 24, y), head, font=f_h, fill=TEXT)
        y += 36
        for line in wrap(d, body, f_b, tw - 24):
            d.text((tx + 24, y), line, font=f_b, fill=MUTED)
            y += 29
        y += 22
    return img


def end_card():
    img = base_canvas()
    d = ImageDraw.Draw(img)
    f_big = font("seguisb.ttf", 62)
    f_lab = font("seguisb.ttf", 20)
    f_val = font("segoeui.ttf", 25)

    d.text((W // 2, 108), "Overrule", font=f_big, fill=TEXT, anchor="mm")
    d.text((W // 2, 168), "Live on studionet — every step verifiable on-chain",
           font=f_val, fill=MUTED, anchor="mm")

    rows = [
        ("REPOSITORY", "github.com/God-jia/genlayer-overrule"),
        ("dApp", "god-jia.github.io/genlayer-overrule"),
        ("CONTRACT", "0x76D56AA824a00B3378c3ADB49224fdFb0376F46c"),
        ("NETWORK", "studionet  ·  chain ID 61999"),
    ]
    y = 250
    for label, value in rows:
        d.rounded_rectangle([190, y, W - 190, y + 78], radius=12, fill=PANEL,
                            outline=BORDER, width=1)
        d.text((222, y + 20), label, font=f_lab, fill=ACCENT)
        d.text((222, y + 46), value, font=f_val, fill=TEXT)
        y += 96

    d.text((W // 2, H - 44), "19 direct-mode tests  ·  real web fetch  ·  real LLM round",
           font=f_lab, fill=MUTED, anchor="mm")
    return img


BULLETS = {
    1: [
        ("Rules are frozen on-chain",
         "A platform publishes a rulebook once. Decisions cite rule ids from it, so the standard can never be edited after the fact."),
        ("Decisions carry evidence",
         "Each decision records the subject, the action, and the content URL validators will re-read later."),
    ],
    2: [
        ("Exactly one appeal",
         "Only the wallet named as the subject can appeal, and only once — enforced by the contract, not policy."),
        ("Argument and evidence on-chain",
         "The appeal text and evidence URLs are stored and shown to every validator."),
    ],
    3: [
        ("Validators re-read the source",
         "At adjudication the contract fetches the live content and the frozen rulebook."),
        ("Model classifies, contract decides",
         "The model labels each cited rule applied / misapplied / unsupported; pure Python maps labels to upheld / overturned / remanded."),
    ],
    4: [
        ("Per-platform overturn rate",
         "Every adjudicated appeal is counted against the platform that issued the decision."),
        ("A number users can't get today",
         "Overturn rate is read straight from contract state — here 1 of 1 decisions overturned."),
    ],
}


def to_array(img):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def build():
    slides = [title_card()]
    slides.append(shot_card(1, "Publish the rulebook, issue a decision",
                            "Platform console — the standard is written on-chain before any decision cites it.",
                            "overrule-1-console.png"))
    slides.append(shot_card(2, "The subject files one appeal",
                            "Appeal tab — the sanctioned wallet contests the decision, once.",
                            "overrule-2-appeal.png"))
    slides.append(shot_card(3, "Validators adjudicate",
                            "Adjudicate tab — the model classifies, the contract derives the outcome in code.",
                            "overrule-3-adjudicate.png"))
    slides.append(shot_card(4, "Transparency the platform can't fake",
                            "Transparency tab — an on-chain overturn rate per platform.",
                            "overrule-4-transparency.png"))
    slides.append(end_card())

    hold = int(HOLD * FPS)
    fade = int(FADE * FPS)

    writer = cv2.VideoWriter(OUT, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    if not writer.isOpened():
        raise SystemExit("VideoWriter could not open")

    frames = [to_array(s) for s in slides]
    for i, frame in enumerate(frames):
        for _ in range(hold - (fade if i < len(frames) - 1 else 0)):
            writer.write(frame)
        if i < len(frames) - 1:
            nxt = frames[i + 1]
            for k in range(fade):
                a = (k + 1) / (fade + 1)
                blended = cv2.addWeighted(frame, 1 - a, nxt, a, 0)
                writer.write(blended)
    writer.release()
    print("wrote", OUT)


if __name__ == "__main__":
    build()
