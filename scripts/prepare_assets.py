#!/usr/bin/env python3
"""Preserve, validate and index already-generated transparent PNG assets.

This utility does not extract or redraw artwork and never enlarges source pixels.
"""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote
import zipfile

from PIL import Image


def resolve_input(value, base):
    text = str(value)
    if sys.platform == 'win32' and re.match(r'^/[A-Za-z]:[\\/]', text):
        text = text[1:]
    path = Path(text).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_preserving(path, data):
    """Reuse identical files, version changed ones, never overwrite an asset."""
    path.parent.mkdir(parents=True, exist_ok=True)
    original_path = path
    version = 2
    while path.exists():
        if path.read_bytes() == data:
            return path
        path = original_path.with_name(f'{original_path.stem}（{version}）{original_path.suffix}')
        version += 1
    path.write_bytes(data)
    return path


def make_index(catalog):
    cards = []
    for item in catalog['assets']:
        label = html.escape(item['label'])
        ident = html.escape(item['id'])
        url = quote(item['png'], safe='/')
        category = html.escape(item.get('category', ''))
        native = ' × '.join(map(str, item['native_size']))
        warnings = '；'.join(html.escape(w) for w in item['warnings'])
        cards.append(f'''<article><a class="visual" href="{url}" download><img src="{url}" alt="{label}"></a>
<h2>{label}</h2><p>{category} · {ident}</p><p>原始尺寸 {native}，输出 {catalog['canvas_size']} × {catalog['canvas_size']}</p>
<p class="warn">{warnings}</p><a href="{url}" download>下载透明PNG</a></article>''')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>可复用图标素材库</title><style>
body{font:15px/1.5 system-ui,"Microsoft YaHei",sans-serif;margin:28px;background:#f4f6f9;color:#17263a}
h1{font-size:26px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:18px}
article{background:white;border:1px solid #dce2ea;border-radius:12px;padding:14px;overflow-wrap:anywhere}
.visual{display:flex;align-items:center;justify-content:center;height:210px;border-radius:8px;background-color:#edf1f6;background-image:linear-gradient(45deg,#dfe5ec 25%,transparent 25%),linear-gradient(-45deg,#dfe5ec 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#dfe5ec 75%),linear-gradient(-45deg,transparent 75%,#dfe5ec 75%);background-size:20px 20px;background-position:0 0,0 10px,10px -10px,-10px 0}
img{max-width:100%;max-height:100%;object-fit:contain}h2{font-size:18px;margin:12px 0 4px}p{font-size:12px;color:#556477;margin:5px 0}a{color:#1d69b9}.warn{color:#8e5d16}
</style><h1>可复用图标素材库</h1><p>点击下载独立PNG。棋盘格仅为网页预览背景，不在PNG文件中。</p><main>''' + ''.join(cards) + '</main></html>'


def prepare(inventory_path, output, canvas_size=1024, padding=64, archive=None,
            library_dir=None):
    inventory_path = Path(inventory_path).resolve()
    output = Path(output).resolve()
    if not 32 <= canvas_size <= 4096 or not 1 <= padding < canvas_size / 2:
        raise ValueError('Canvas must be 32..4096 pixels, with padding > 0 and < half the canvas')
    inventory = json.loads(inventory_path.read_text(encoding='utf-8-sig'))
    entries = inventory.get('assets')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Inventory must contain a non-empty assets array')
    ids = set()
    for entry in entries:
        ident = entry.get('id', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,79}', ident) or ident in ids:
            raise ValueError(f'Invalid or duplicate asset ID: {ident!r}')
        ids.add(ident)
        if not isinstance(entry.get('label'), str) or not re.fullmatch(r'[\u3400-\u9fff]+', entry['label']):
            raise ValueError(f'{ident}: label must be a short Chinese description using only Chinese characters')
        if entry.get('provenance') not in ('imagegen', 'provided'):
            raise ValueError(f'{ident}: provenance (imagegen/provided) required')
        if entry['provenance'] == 'imagegen' and not entry.get('prompt_path'):
            raise ValueError(f'{ident}: imagegen assets require their actual prompt_path')
    output.mkdir(parents=True, exist_ok=True)
    records = []
    library_pngs = []
    files = set()
    for entry in entries:
        ident = entry['id']
        source = resolve_input(entry['input_png'], inventory_path.parent)
        original = source.read_bytes()
        with Image.open(io.BytesIO(original)) as opened:
            if opened.format != 'PNG':
                raise ValueError(f'{ident}: input must be a PNG')
            image = opened.convert('RGBA')
        alpha = image.getchannel('A')
        if alpha.getextrema()[0] != 0 or not alpha.getbbox():
            raise ValueError(f'{ident}: input must have a non-empty subject and true transparent background')
        bbox = alpha.getbbox()
        x0, y0, x1, y1 = bbox
        warnings = []
        native_edge = max(x1 - x0, y1 - y0)
        if native_edge < 512:
            warnings.append('原生前景长边不足512像素，未插值放大；按使用尺寸检查细节')
        subject = image.crop(bbox)
        factor = min(1.0, (canvas_size - 2 * padding) / max(subject.size))
        if factor < 1:
            subject = subject.resize((max(1, round(subject.width * factor)), max(1, round(subject.height * factor))), Image.Resampling.LANCZOS)
        packed = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        packed.alpha_composite(subject, ((canvas_size - subject.width) // 2, (canvas_size - subject.height) // 2))
        packed_alpha = packed.getchannel('A')
        content_box = packed_alpha.getbbox()
        if min(content_box[0], content_box[1], canvas_size - content_box[2], canvas_size - content_box[3]) < padding:
            raise ValueError(f'{ident}: insufficient transparent padding after packing')
        buffer = io.BytesIO()
        packed.save(buffer, format='PNG', optimize=True)
        raw_path = write_preserving(output / 'raw' / f'{ident}--{sha256(original)[:12]}.png', original)
        png_path = write_preserving(output / 'png' / f'{entry["label"]}.png', buffer.getvalue())
        files.update([raw_path, png_path])
        record = {k: entry[k] for k in ('id', 'label', 'category', 'provenance', 'source_regions', 'notes') if k in entry}
        record.update({'png': png_path.relative_to(output).as_posix(), 'raw': raw_path.relative_to(output).as_posix(),
                       'source_sha256': sha256(original), 'png_sha256': sha256(buffer.getvalue()),
                       'native_size': list(image.size), 'native_content_box': list(bbox),
                       'native_foreground_long_edge': native_edge, 'output_size': [canvas_size, canvas_size],
                       'content_box': list(content_box), 'scale_factor': factor, 'scaled_up': False,
                       'transparent': True, 'warnings': warnings})
        if entry.get('prompt_path'):
            prompt = resolve_input(entry['prompt_path'], inventory_path.parent).read_bytes()
            prompt_path = write_preserving(output / 'prompts' / f'{ident}.txt', prompt)
            files.add(prompt_path)
            record['prompt_path'] = prompt_path.relative_to(output).as_posix()
        if library_dir is not None and entry['provenance'] == 'imagegen':
            library_path = write_preserving(Path(library_dir) / png_path.name, buffer.getvalue())
            library_pngs.append(str(library_path.resolve()))
        records.append(record)
    catalog = {'schema_version': 1, 'canvas_size': canvas_size, 'padding': padding,
               'source_images': inventory.get('source_images', []), 'assets': records}
    catalog_path = output / 'catalog.json'
    index_path = output / 'index.html'
    # These two indexes describe the current inventory; preserved asset files are never deleted.
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    index_path.write_text(make_index(catalog), encoding='utf-8')
    files.update([catalog_path, index_path])
    archive_path = None
    if archive:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(files):
                z.write(f, f.relative_to(output).as_posix())
        archive_path = write_preserving(Path(archive).resolve(), zip_buffer.getvalue())
    return {'asset_count': len(records), 'catalog': str(catalog_path), 'index': str(index_path),
            'archive': str(archive_path) if archive_path else None,
            'library_pngs': library_pngs,
            'warnings': {r['id']: r['warnings'] for r in records if r['warnings']}}


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--canvas-size', type=int, default=1024)
    parser.add_argument('--padding', type=int, default=64)
    parser.add_argument('--zip', dest='archive')
    parser.add_argument('--library-dir', type=Path, help='Optional flat directory for redrawn PNG copies')
    args = parser.parse_args()
    try:
        result = prepare(args.inventory, args.output, args.canvas_size, args.padding, args.archive, args.library_dir)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f'Asset preparation failed: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
