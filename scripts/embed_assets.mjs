import fs from 'node:fs/promises';
import path from 'node:path';

/** Insert original PNG artwork as separate, aspect-preserving native picture objects.
 * Pass sharp from the current presentation runtime. Only transparent outer padding
 * is trimmed in the embedded copy; the reusable library files remain untouched.
 */
export async function createAssetPlacer({catalogPath, sharp}) {
  if (typeof sharp !== 'function') throw new Error('Pass sharp from the current presentation runtime');
  const base = path.dirname(path.resolve(catalogPath));
  const catalog = JSON.parse(await fs.readFile(catalogPath, 'utf8'));
  const items = new Map(catalog.assets.map(item => [item.id, item]));
  if (items.size !== catalog.assets.length) throw new Error('Duplicate IDs in asset catalog');
  const cache = new Map();
  return async function placeAsset(slide, id, frame, {trim = true, alt} = {}) {
    const item = items.get(id);
    if (!item) throw new Error(`Unknown asset ID: ${id}`);
    const {left, top, width, height} = frame;
    if (![left, top, width, height].every(Number.isFinite) || width <= 0 || height <= 0) {
      throw new Error(`Invalid frame for ${id}`);
    }
    const key = `${id}:${trim}`;
    if (!cache.has(key)) {
      const source = path.resolve(base, item.png);
      const original = await fs.readFile(source);
      const metadata = await sharp(original).metadata();
      let w = metadata.width, h = metadata.height, data = original;
      if (trim) {
        const box = item.content_box;
        if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isInteger)) throw new Error(`Missing or invalid content_box: ${id}`);
        const [l, t, r, b] = box;
        if (l < 0 || t < 0 || r > w || b > h || r <= l || b <= t) throw new Error(`Invalid content_box bounds: ${id}`);
        data = await sharp(original).extract({left:l, top:t, width:r-l, height:b-t}).png().toBuffer();
        w = r-l; h = b-t;
      }
      cache.set(key, {data:new Uint8Array(data), width:w, height:h});
    }
    const image = cache.get(key);
    const scale = Math.min(width/image.width, height/image.height);
    const w = image.width*scale, h = image.height*scale;
    return slide.images.add({blob:image.data, contentType:'image/png', fit:'contain',
      alt:alt ?? `${item.label} (${id})`,
      position:{left:left+(width-w)/2, top:top+(height-h)/2, width:w, height:h}});
  };
}
