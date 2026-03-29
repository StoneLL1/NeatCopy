"""预览面板窗口组件：显示 LLM 处理结果，支持编辑和应用到剪贴板。"""
import ctypes
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint
from PyQt6.QtGui import QCursor, QMouseEvent

# 边框拖动区域宽度（像素）
_EDGE_SIZE = 6


class PreviewWindow(QWidget):
    """LLM 结果预览面板，置顶悬浮窗，毛玻璃效果。"""

    apply_to_clipboard = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._current_result = ""
        self._current_prompt = ""
        self._drag_pos = None
        self._resize_timer = None
        self._resize_edge = None  # 当前拖动的边框方向
        self._resize_start_geo = None  # resize 起始几何
        self._resize_start_pos = None  # resize 起始鼠标位置

        self._setup_window_properties()
        self._create_ui()
        self._apply_acrylic_effect()

    # ================================================================
    #  窗口属性
    # ================================================================

    def _setup_window_properties(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(
            self._config.get('preview.window_width', 360),
            self._config.get('preview.window_height', 260)
        )
        self.setMinimumSize(240, 180)

    # ================================================================
    #  UI 构建
    # ================================================================

    def _create_ui(self):
        # --- 外层容器：提供边框拖动区域 ---
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- 内容容器（带内边距的圆角面板） ---
        container = QWidget()
        container.setObjectName("panel")
        container.setStyleSheet("""
            #panel {
                background: rgba(32, 32, 32, 210);
                border: 1px solid rgba(80, 80, 80, 140);
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        # === 顶部栏：可拖动区域 + 状态 + 关闭按钮 ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        # 状态指示点
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(12)
        self.status_dot.setStyleSheet("color: #666; font-size: 10px;")
        top_bar.addWidget(self.status_dot)

        # 状态文字
        self.status_label = QLabel("等待处理")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setStyleSheet("""
            #statusLabel {
                color: #999;
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 0.3px;
            }
        """)
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()

        # 关闭按钮
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setStyleSheet("""
            #closeBtn {
                background: transparent;
                border: none;
                font-size: 12px;
                color: #777;
                border-radius: 4px;
            }
            #closeBtn:hover {
                background: rgba(255, 255, 255, 25);
                color: #ccc;
            }
        """)
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)

        # 整个顶栏可拖动
        self._top_bar_widget = container  # 备用
        layout.addLayout(top_bar)

        # === 文本编辑区 ===
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("等待 LLM 处理结果…")
        self.text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: rgba(18, 18, 18, 200);
                border: 1px solid rgba(70, 70, 70, 100);
                border-radius: 6px;
                padding: 8px;
                color: #ddd;
                font-size: 13px;
                selection-background-color: rgba(100, 149, 237, 100);
            }
            QTextEdit:focus {
                border: 1px solid rgba(100, 149, 237, 150);
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(120, 120, 120, 100);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        layout.addWidget(self.text_edit, stretch=1)

        # === 底部栏：prompt 名称 + 应用按钮 ===
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        # Prompt 名称
        self.prompt_label = QLabel("")
        self.prompt_label.setObjectName("promptLabel")
        self.prompt_label.setStyleSheet("""
            #promptLabel {
                color: #666;
                font-size: 10px;
            }
        """)
        bottom_bar.addWidget(self.prompt_label)
        bottom_bar.addStretch()

        # 应用按钮
        self.apply_btn = QPushButton("应用到剪贴板")
        self.apply_btn.setObjectName("applyBtn")
        self.apply_btn.setFixedHeight(30)
        self.apply_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.apply_btn.setStyleSheet("""
            #applyBtn {
                background: rgba(80, 80, 80, 160);
                color: #ccc;
                border: 1px solid rgba(100, 100, 100, 100);
                border-radius: 6px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            #applyBtn:hover {
                background: rgba(100, 100, 100, 180);
                color: #eee;
                border: 1px solid rgba(130, 130, 130, 140);
            }
            #applyBtn:pressed {
                background: rgba(60, 60, 60, 200);
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        bottom_bar.addWidget(self.apply_btn)

        layout.addLayout(bottom_bar)

        outer.addWidget(container)

    def _apply_acrylic_effect(self):
        if sys.platform != 'win32':
            return

        version = sys.getwindowsversion()
        if version.major < 10 or (version.major == 10 and version.build < 22000):
            # Win10 降级：深色半透明背景
            self.setStyleSheet("#panel { background: rgba(32, 32, 32, 235); }")
            return

        hwnd = int(self.winId())
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        value = 3  # Acrylic

        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(ctypes.c_int(value)),
                4
            )
        except Exception:
            self.setStyleSheet("#panel { background: rgba(32, 32, 32, 235); }")

    # ================================================================
    #  公共方法
    # ================================================================

    def _on_apply_clicked(self):
        text = self.text_edit.toPlainText()
        if text:
            self.apply_to_clipboard.emit(text)
            self.set_status("已应用")

    def update_result(self, result: str, prompt_name: str):
        self._current_result = result
        self._current_prompt = prompt_name
        self.text_edit.setPlainText(result)
        self.prompt_label.setText(f"Prompt: {prompt_name}" if prompt_name else "")
        self.set_status("处理完成")

    def set_status(self, status: str):
        self.status_label.setText(status)
        color_map = {
            "等待处理": "#666",
            "处理中…": "#f0ad4e",
            "处理完成": "#5cb85c",
            "处理失败": "#d9534f",
            "已应用": "#5bc0de",
        }
        color = color_map.get(status, "#999")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.status_label.setStyleSheet(f"""
            #statusLabel {{
                color: {color};
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 0.3px;
            }}
        """)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()
            self.raise_()

    # ================================================================
    #  拖动 + Resize（通过鼠标事件）
    # ================================================================

    def _edge_at(self, pos: QPoint) -> str | None:
        """判断鼠标位置处于哪个边框拖动区域。"""
        r = self.rect()
        x, y = pos.x(), pos.y()
        w, h = r.width(), r.height()
        e = _EDGE_SIZE

        on_left = x < e
        on_right = x > w - e
        on_top = y < e
        on_bottom = y > h - e

        if on_top and on_left:
            return "top_left"
        if on_top and on_right:
            return "top_right"
        if on_bottom and on_left:
            return "bottom_left"
        if on_bottom and on_right:
            return "bottom_right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        if on_left:
            return "left"
        if on_right:
            return "right"
        return None

    @staticmethod
    def _cursor_for_edge(edge: str) -> Qt.CursorShape:
        cursors = {
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top_left": Qt.CursorShape.SizeFDiagCursor,
            "bottom_right": Qt.CursorShape.SizeFDiagCursor,
            "top_right": Qt.CursorShape.SizeBDiagCursor,
            "bottom_left": Qt.CursorShape.SizeBDiagCursor,
        }
        return cursors.get(edge, Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edge = self._edge_at(pos)
            if edge:
                # 开始 resize
                self._resize_edge = edge
                self._resize_start_geo = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                return
            else:
                # 开始拖动（整个窗口区域都可拖，除了文本编辑区）
                child = self.childAt(pos)
                if child is not self.text_edit and not self.text_edit.isAncestorOf(child):
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_edge and self._resize_start_geo and self._resize_start_pos:
            # --- Resize 逻辑 ---
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            edge = self._resize_edge

            if "left" in edge:
                geo.setLeft(geo.left() + delta.x())
            if "right" in edge:
                geo.setRight(geo.right() + delta.x())
            if "top" in edge:
                geo.setTop(geo.top() + delta.y())
            if "bottom" in edge:
                geo.setBottom(geo.bottom() + delta.y())

            # 强制最小尺寸
            if geo.width() < self.minimumWidth():
                if "left" in edge:
                    geo.setLeft(geo.right() - self.minimumWidth())
                else:
                    geo.setRight(geo.left() + self.minimumWidth())
            if geo.height() < self.minimumHeight():
                if "top" in edge:
                    geo.setTop(geo.bottom() - self.minimumHeight())
                else:
                    geo.setBottom(geo.top() + self.minimumHeight())

            self.setGeometry(geo)
            return

        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            return

        # 更新光标形状
        edge = self._edge_at(event.position().toPoint())
        if edge:
            self.setCursor(QCursor(self._cursor_for_edge(edge)))
        else:
            self.unsetCursor()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = None
        self._resize_start_geo = None
        self._resize_start_pos = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_timer is None:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._save_window_size)
        self._resize_timer.start(500)

    def _save_window_size(self):
        self._config.set('preview.window_width', self.width())
        self._config.set('preview.window_height', self.height())
