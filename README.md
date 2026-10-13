# image-assets-to-ppt

将框架图和流程图以及信息图重建为可编辑 PowerPoint，同时保留独立高清透明 PNG 图标素材。

这是一套面向 Codex 的技能说明和辅助脚本。图标通过可用的图像生成工具逐个重绘；文字和常规结构通过演示文稿工具重建为原生对象。它不是单命令全自动转换器，也不会将 PNG 内部路径转换为矢量。

## 能力

- 独立透明 PNG 图标使用简短中文语义名称
- 保留原始输入和实际提示词以及素材清单
- 生成可浏览素材目录和素材 ZIP
- 可将本次重绘 PNG 额外平铺复制到指定目录
- 同名不同内容自动编号保存，避免覆盖旧素材
- PPT 中的文字和形状以及表格和流程连接器使用原生对象

## 安装技能

将此仓库复制到你的 Codex 技能目录下的 `image-assets-to-ppt` 文件夹，确保 `SKILL.md` 位于该文件夹根目录。在支持技能的会话中使用 `$image-assets-to-ppt` 并提供参考图片。

完整重绘流程需要当前环境提供 `imagegen` 和 `presentations` 技能以及相应工具。启动脚本使用 `load_workspace_dependencies` 返回的 Python 和相邻 Node 依赖。本仓库不分发这些工具或运行时；只有素材整理脚本可以仅依赖 Python 和 Pillow 独立运行。

## 独立整理 PNG

Python 3.9 或更新版本：

```sh
python -m pip install -r requirements.txt
python scripts/prepare_assets.py --inventory inventory.json --output assets --zip assets.zip
```

需要额外平铺副本时显式指定目录：

```sh
python scripts/prepare_assets.py --inventory inventory.json --output assets --library-dir icon-library
```

未指定 `--library-dir` 时不会向额外目录写文件。该目录只收到清单中 `provenance` 为 `imagegen` 的最终透明 PNG；复用的现成素材不额外复制。文件名来自仅含汉字的 `label`，内部英文 `id` 保持稳定。清单字段和完整示例见 [图标重绘与清单](references/asset-workflow.md)。输入 PNG 须具有真实透明背景并保留非空主体，脚本不会生成图标或修复缺失细节。

## 检查

```sh
python scripts/self_check.py --assets-only
```

该检查在临时目录中验证中文命名和额外复制以及透明度和文件保留，不访问实际业务素材。使用 Codex 提供的 Python 运行 `python scripts/self_check.py` 可同时检查演示文稿运行时启动流程。

## 文件

- [SKILL.md](SKILL.md)：技能入口
- [references/asset-workflow.md](references/asset-workflow.md)：图标重绘和素材清单
- [references/ppt-workflow.md](references/ppt-workflow.md)：PPT 重建和验收
- `scripts/prepare_assets.py`：PNG 整理和导出
- `scripts/embed_assets.mjs`：将独立 PNG 插入 Artifact Tool 幻灯片
- `scripts/run_presentation.py`：启动当前提供的演示文稿运行时
- `scripts/self_check.py`：脚本自检

本仓库只包含技能说明和辅助脚本，不包含私人图片或生成素材或账户凭据。已移除固定本机导出路径，实际目录由调用者指定。

采用 [MIT 许可证](LICENSE)。参考图片和图标的授权由使用者自行确认；仓库许可证不改变第三方素材的权利。
