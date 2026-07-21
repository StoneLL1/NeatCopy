# NeatCopy macOS 版

## 安装

双击 `release-macos/NeatCopy-*-macOS-arm64.dmg`，将 NeatCopy 拖入 Applications。
当前构建默认是 Apple Silicon（arm64）版本，未使用 Apple Developer 证书签名或公证。

轮盘、预览和历史记录快捷键使用 macOS 系统热键注册，不需要隐私权限。

“处理剪贴板”快捷键需要先向当前应用发送一次 `⌘C` 来取得选中文本，首次运行时需要打开：

`系统设置 → 隐私与安全性 → 辅助功能`

将 NeatCopy 加入并允许。当前 macOS 安装包使用稳定的应用授权身份，后续覆盖升级不会再因二进制哈希变化而自动丢失授权。如果开关已打开但“处理剪贴板”仍无效，请先删除旧的 NeatCopy 条目，再重新添加 `/Applications/NeatCopy.app`。

如果启用了可选的“双击 `⌘C`”，还需要打开：

`系统设置 → 隐私与安全性 → 输入监控`

这是只读键盘监听权限，只用于识别两次完整的 `⌘C`。应用不会上传键盘内容。“处理剪贴板”会等待原快捷键完全释放并确认剪贴板确实更新后，才弹出轮盘；双击复制也会等待第二次复制完成，不使用固定延迟处理旧内容。

轮盘使用独立的 macOS 置顶窗口，不依赖 NeatCopy 已处于前台；从任意应用触发时会短暂取得键盘焦点以支持数字键和 `Esc`，关闭后自动将焦点还给原应用。

设置页会按物理按键记录 macOS 快捷键：物理 `Control` 保存为 `ctrl`，物理 `Command` 保存为 `cmd`，不会因 Qt 的跨平台修饰键语义而互换。

macOS 默认快捷键：

- 处理剪贴板：`⌘⇧C`
- Prompt 轮盘：`⌘⇧P`
- 预览面板：`Control+Q`
- 历史记录：`Control+H`
- 双击复制触发：连按两次 `⌘C`（默认关闭）

预览和历史使用 `Control` 是为了不拦截 macOS 系统级的 `⌘Q`（退出）与 `⌘H`（隐藏）。

## 数据位置

- 配置：`~/Library/Application Support/NeatCopy/config.json`
- 历史：`~/Library/Application Support/NeatCopy/history.json`
- 运行诊断：`~/Library/Application Support/NeatCopy/runtime.log`
- 崩溃日志：`~/Library/Application Support/NeatCopy/crash.log`
- 开机启动：`~/Library/LaunchAgents/com.stonell1.neatcopy.plist`

## 从源码构建

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
installer/build_macos.sh
```

最终安装包位于 `release-macos/`。如果要发布到其他用户的 Mac，建议后续使用 Apple Developer 证书完成 codesign 与 notarization，以减少 Gatekeeper 提示。
