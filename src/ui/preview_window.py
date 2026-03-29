"""预览面板窗口组件：显示 LLM 处理结果，支持编辑和应用到剪贴板。"""
import ctypes
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QSizeGrip
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class PreviewWindow(QWidget):
    """LLM 结果预览面板，置顶悬浮窗，毛玻璃效果。"""

    # 信号：用户点击应用按钮时发射，携带编辑后的文本
    apply_to_clipboard = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self._config = config  # ConfigManager 实例
        self._current_result = ""
        self._current_prompt = ""
        self._drag_pos = None
        self._resize_timer = None  # 延迟保存尺寸

        self._setup_window_properties()
        self._create_ui()
        self._apply_acrylic_effect()

    def _setup_window_properties(self):
        """设置窗口属性：无边框、置顶、半透明背景。"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 从配置读取尺寸
        self.resize(
            self._config.get('preview.window_width', 320),
            self._config.get('preview.window_height', 200)
        )

        # 设置最小尺寸
        self.setMinimumSize(200, 150)

    def _create_ui(self):
        """创建 UI 布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # === 顶部栏：状态 + 关闭按钮 ===
        top_bar = QHBoxLayout()

        self.status_label = QLabel("等待处理")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        top_bar.addWidget(self.status_label)

        top_bar.addStretch()

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                color: #666;
            }
            QPushButton:hover {
                background: #e81123;
                color: white;
                border-radius: 4px;
            }
        """)
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)

        layout.addLayout(top_bar)

        # === 文本编辑区 ===
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("等待 LLM 处理结果...")
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(200, 200, 200, 0.4);
                border-radius: 4px;
                padding: 4px;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.text_edit, stretch=1)

        # === Prompt 名称栏 ===
        self.prompt_label = QLabel("")
        self.prompt_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.prompt_label)

        # === 应用按钮 ===
        self.apply_btn = QPushButton("应用到剪贴板")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1084d8;
            }
            QPushButton:pressed {
                background: #006cbd;
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        layout.addWidget(self.apply_btn)

        # === 右下角尺寸调整手柄 ===
        size_grip = QSizeGrip(self)
        layout.addWidget(size_grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

    def _apply_acrylic_effect(self):
        """应用 Windows 11 毛玻璃效果（Acrylic）。"""
        # Windows 版本检测
        if sys.platform != 'win32':
            return

        # Windows 10 不支持 Acrylic，需要版本检测
        version = sys.getwindowsversion()
        if version.major < 10 or (version.major == 10 and version.build < 22000):
            # Windows 10 或更早版本，降级为半透明背景
            self.setStyleSheet("background: rgba(240, 240, 240, 0.85);")
            return

        # Windows 11 Acrylic 效果
        hwnd = int(self.winId())
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        value = 3  # Acrylic effect

        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(ctypes.c_int(value)),
                4
            )
        except Exception:
            # API 调用失败，降级为半透明
            self.setStyleSheet("background: rgba(240, 240, 240, 0.85);")

    def _on_apply_clicked(self):
        """应用按钮点击：发射信号将文本写入剪贴板。"""
        text = self.text_edit.toPlainText()
        if text:
            self.apply_to_clipboard.emit(text)
            self.set_status("已应用 ✓")

    # === 公共方法 ===

    def update_result(self, result: str, prompt_name: str):
        """更新处理结果。"""
        self._current_result = result
        self._current_prompt = prompt_name
        self.text_edit.setPlainText(result)
        self.prompt_label.setText(f"Prompt: {prompt_name}")
        self.set_status("处理完成")

    def set_status(self, status: str):
        """设置状态栏文本。"""
        self.status_label.setText(status)

    def toggle_visibility(self):
        """切换显示/隐藏（toggle 行为）。"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()
            self.raise_()  # 确保置顶

    # === 拖动实现 ===

    def mousePressEvent(self, event):
        """记录拖动起始位置。"""
        if event.button() == Qt.MouseButton.LeftButton:
            # PyQt6 使用 globalPosition() 返回 QPointF
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """拖动窗口。"""
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """结束拖动。"""
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        """窗口尺寸变化时延迟保存到配置（避免频繁写入）。"""
        super().resizeEvent(event)

        # 使用延迟保存，避免 resize 过程中频繁写入
        if self._resize_timer is None:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_window_size)

        self._resize_timer.start(500)  # 500ms 延迟

    def _save_window_size(self):
        """保存窗口尺寸到配置。"""
        self._config.set('preview.window_width', self.width())
        self._config.set('preview.window_height', self.height())