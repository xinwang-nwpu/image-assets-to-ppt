"""Regression check for PNG exports, preservation and the local runtime launcher."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from PIL import Image, ImageDraw


def main(assets_only=False):
    scripts=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('prepare_assets',scripts/'prepare_assets.py')
    assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
    with TemporaryDirectory(prefix='image-assets-check-') as folder:
        root=Path(folder);source=root/'edge.png'
        image=Image.new('RGBA',(600,600),(0,0,0,0))
        ImageDraw.Draw(image).rectangle((0,25,200,580),fill=(255,255,255,255))
        image.save(source);original=source.read_bytes()
        generated=root/'generated.png';generated.write_bytes(original)
        prompt=root/'prompt.txt';prompt.write_text('重绘规划智能体并保留透明背景',encoding='utf-8')
        inventory=root/'inventory.json'
        entries=[dict(id='edge',label='边缘图标',input_png=str(source),provenance='provided'),
                 dict(id='planner',label='规划智能体',input_png=str(generated),provenance='imagegen',prompt_path=str(prompt))]
        inventory.write_text(json.dumps({'assets':entries}),encoding='utf-8')
        library=root/'矢量素材库'
        report=assets.prepare(inventory,root/'assets',library_dir=library)
        assert report['warnings']=={},report
        assert source.read_bytes()==original
        catalog=json.loads((root/'assets/catalog.json').read_text(encoding='utf-8'))
        record=catalog['assets'][0];png=Image.open(root/'assets'/record['png'])
        assert png.getpixel((512,512))==(255,255,255,255)
        assert png.getpixel((0,0))[3]==0
        assert Path(record['png']).name=='边缘图标.png'
        exported=library/'规划智能体.png';exported_bytes=exported.read_bytes()
        assert exported_bytes==(root/'assets/png/规划智能体.png').read_bytes()
        assert report['library_pngs']==[str(exported.resolve())]
        task_only=assets.prepare(inventory,root/'task-only')
        assert task_only['library_pngs']==[]
        cli=subprocess.run([sys.executable,str(scripts/'prepare_assets.py'),
                            '--inventory',str(inventory),'--output',str(root/'cli-assets'),
                            '--library-dir',str(root/'cli-library')],capture_output=True,text=True,encoding='utf-8',check=True)
        cli_report=json.loads(cli.stdout)
        assert cli_report['library_pngs']==[str((root/'cli-library/规划智能体.png').resolve())]
        assert [p.name for p in (root/'cli-library').iterdir()]==['规划智能体.png']
        assets.prepare(inventory,root/'assets',library_dir=library)
        assert list(library.iterdir())==[exported]
        ImageDraw.Draw(image).rectangle((0,25,200,580),fill=(0,0,0,255));image.save(generated)
        assets.prepare(inventory,root/'assets',library_dir=library)
        assert exported.read_bytes()==exported_bytes
        assert {p.name for p in library.iterdir()}=={'规划智能体.png','规划智能体（2）.png'}
        assert (library/'规划智能体（2）.png').read_bytes()==(root/'assets/png/规划智能体（2）.png').read_bytes()
        entries[0]['label']='../unsafe'
        inventory.write_text(json.dumps({'assets':entries}),encoding='utf-8')
        try:
            assets.prepare(inventory,root/'invalid',library_dir=library)
        except ValueError as exc:
            assert 'Chinese description' in str(exc)
        else:
            raise AssertionError('Unsafe filename was accepted')
        entries[0]['label']='边缘图标'
        inventory.write_text(json.dumps({'assets':entries}),encoding='utf-8')
        Image.new('RGB',(600,600),'white').save(source)
        try:
            assets.prepare(inventory,root/'invalid',library_dir=library)
        except ValueError as exc:
            assert 'transparent background' in str(exc)
        else:
            raise AssertionError('Opaque input was accepted')
        if assets_only:
            print('PASS: PNG export checks passed; presentation runtime checks skipped (--assets-only).')
            return
        env=os.environ.copy()
        for key in ('SystemRoot','WINDIR','RUNTIME_NODE','RUNTIME_NODE_MODULES','CODEX_PRIMARY_RUNTIME_NODE_MODULES'):
            env.pop(key,None)
        probe=subprocess.run([sys.executable,str(scripts/'run_presentation.py'),'--preflight'],env=env,capture_output=True,text=True,check=True)
        result=json.loads(probe.stdout.strip());assert result['ok'] and Path(result['modules']).is_dir()
        if os.name=='nt':
            assert Path(result['SystemRoot']).is_dir() and Path(result['WINDIR']).is_dir()
        forwarded=subprocess.run([sys.executable,str(scripts/'run_presentation.py'),'--cwd',str(root),'--','-e','process.stdout.write(process.cwd())'],env=env,capture_output=True,text=True,check=True)
        assert Path(forwarded.stdout).resolve()==root.resolve()
    print('PASS: Chinese PNG names; flat generated-only library; duplicate reuse and collision preservation; transparency and originals preserved; runtime checks passed.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-only',action='store_true',help='Check PNG exports without the Codex presentation runtime')
    main(parser.parse_args().assets_only)
