from __future__ import annotations

from pathlib import Path
from typing import Protocol
from PIL import Image, ImageDraw, ImageFont, ImageOps
from ..models import WIDTH, HEIGHT, RenderError

def wrap(text, font, width):
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for c in paragraph:
            if line and font.getlength(line + c) > width:
                lines.append(line)
                line = ''
            line += c
        lines.append(line)
    return lines


def placeholder(scene, font_path, path):
    palette = {'image': '#172b40', 'video': '#252440', 'broll': '#173d36',
               'title_card': '#252a32', 'quote_card': '#382a30'}
    image = Image.new('RGB', (WIDTH, HEIGHT), palette[scene['visual']['type']])
    draw = ImageDraw.Draw(image)
    for i in range(8):
        x, y = 100 + i*110, 260 + i*145
        draw.ellipse((x-120, y-120, x+180, y+180), outline='#40566a', width=3)
    if font_path is None:
        image.save(path)
        return
    label_font = ImageFont.truetype(str(font_path), 30)
    draw.text((100, 110), f"{scene['id']} | {scene['visual']['type']}", font=label_font, fill='#b8c7d6')
    draw.text((100, 175), 'MVP PLACEHOLDER', font=label_font, fill='#b8c7d6')
    image = draw_onscreen_text(image, scene, font_path)
    draw = ImageDraw.Draw(image)
    draw.text((100, 1620), '程序生成占位画面 · 非真实素材', font=label_font, fill='#b8c7d6')
    image.save(path)


def draw_onscreen_text(image, scene, font_path):
    if font_path is None:
        return image
    draw = ImageDraw.Draw(image)
    for size in range(58, 23, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap(scene['onscreen_text'], font, WIDTH-240)
        if len(lines) * (size+22) <= 650:
            break
    else:
        raise RenderError('onscreen_text too long to fit without truncation')
    y = 730 - len(lines) * (size+22) // 2
    for line in lines:
        draw.text(((WIDTH-font.getlength(line))/2, y), line, font=font,
                  fill='#fff4db', stroke_width=max(2, size//18), stroke_fill='#111820')
        y += size+22
    return image



def create_text_overlay(scene, font_path, path):
    """Create a transparent overlay with the exact storyboard onscreen_text."""
    image = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    if font_path is None:
        image.save(path)
        return path
    draw = ImageDraw.Draw(image)
    for size in range(58, 23, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap(scene['onscreen_text'], font, WIDTH-240)
        if len(lines) * (size+22) <= 650:
            break
    else:
        raise RenderError('onscreen_text too long to fit without truncation')
    y = 730 - len(lines) * (size+22) // 2
    for line in lines:
        draw.text(
            ((WIDTH-font.getlength(line))/2, y),
            line,
            font=font,
            fill=(255, 244, 219, 255),
            stroke_width=max(2, size//18),
            stroke_fill=(17, 24, 32, 255),
        )
        y += size+22
    image.save(path)
    return path


def find_visual_asset(assets_dir, scene_id):
    if assets_dir is None:
        return None
    extensions = ('.png', '.jpg', '.jpeg', '.webp')
    matches = [Path(assets_dir)/(scene_id + ext) for ext in extensions
               if (Path(assets_dir)/(scene_id + ext)).is_file()]
    if len(matches) > 1:
        raise RenderError(
            f'{scene_id}: multiple visual assets found; keep exactly one of '
            'PNG, JPG, JPEG, or WebP.'
        )
    return matches[0] if matches else None


def normalize_image_asset(source, destination):
    try:
        with Image.open(source) as opened:
            opened = ImageOps.exif_transpose(opened)
            if opened.mode in ('RGBA', 'LA') or 'transparency' in opened.info:
                rgba = opened.convert('RGBA')
                background = Image.new('RGBA', rgba.size, (24, 32, 42, 255))
                background.alpha_composite(rgba)
                image = background.convert('RGB')
            else:
                image = opened.convert('RGB')
            fitted = ImageOps.fit(
                image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )
            fitted.save(destination, format='PNG')
    except Exception as exc:
        raise RenderError(f'Cannot load visual asset {source}: {exc}') from exc


def prepare_visual(scene, font_path, destination, visual_asset=None):
    if visual_asset is None:
        if scene['visual']['type'] in ('video', 'broll'):
            from .video import StaticVideoFallback
            StaticVideoFallback().generate_video(scene, font_path, destination)
        else:
            PlaceholderImage().generate_image(scene, font_path, destination)
        return True
    normalize_image_asset(visual_asset, destination)
    with Image.open(destination) as opened:
        image = opened.convert('RGB')
    image = draw_onscreen_text(image, scene, font_path)
    image.save(destination)
    return False


class ImageProvider(Protocol):
    def generate_image(self, scene: dict, font_path: Path | None, output_path: Path) -> Path: ...


class PlaceholderImage:
    """Deterministic local graphics, with exact source text when a font is available."""
    cache_key = 'placeholder-v2'

    def generate_image(self, scene, font_path, output_path):
        placeholder(scene, font_path, output_path)
        return output_path
