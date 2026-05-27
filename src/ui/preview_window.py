"""预览面板窗口组件：显示 LLM 处理结果，支持编辑和应用到剪贴板。支持深色/浅色主题切换。"""
import ctypes
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint
from PyQt6.QtGui import QCursor

from ui.styles import ColorPalette

# 边框拖动区域宽度（像素）
_EDGE_SIZE = 6


class PreviewWindow(QWidget):
    """LLM 结果预览面板，置顶悬浮窗，毛玻璃效果，支持深色/浅色主题。"""

    apply_to_clipboard = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._current_result = ""
        self._current_prompt = ""
        self._drag_pos = None
        self._resize_timer = None
        self._resize_edge = None
        self._resize_start_geo = None
        self._resize_start_pos = None
        self._theme = config.get('preview.theme', 'dark')

        self._setup_window_properties()
        self._create_ui()
        self._apply_theme(self._theme)
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
            self._config.get('preview.window_width', 480),
            self._config.get('preview.window_height', 260)
        )
        self.setMinimumSize(240, 180)

    # ================================================================
    #  主题样式
    # ================================================================

    def _get_theme_styles(self, theme: str) -> dict:
        """返回指定主题的样式配置字典。基于 Shadcn ColorPalette + 预览面板专用透明度色。"""
        c = ColorPalette.get(theme)

        # 状态点颜色：统一使用 palette 语义色
        status_colors = {
            'status_waiting': c['muted'],
            'status_processing': c['warn'],
            'status_done': c['success'],
            'status_failed': c['danger'],
            'status_applied': c['info'],
        }

        if theme == 'light':
            return {
                'panel_bg': 'rgba(255, 255, 255, 0.92)',
                'panel_border': 'rgba(0, 0, 0, 0.08)',
                'edit_bg': 'rgba(249, 250, 251, 0.88)',
                'edit_border': 'rgba(0, 0, 0, 0.08)',
                'edit_focus_border': c['accent'],
                'edit_text': c['fg'],
                'edit_placeholder': c['muted'],
                'edit_selection': 'rgba(0, 0, 0, 0.08)',
                'scrollbar_bg': c['scrollbar_bg'],
                'scrollbar_handle': c['scrollbar_handle'],
                **status_colors,
                'prompt_text': c['muted'],
                'btn_bg': c['accent'],
                'btn_border': c['accent'],
                'btn_text': c['accent_on'],
                'btn_hover_bg': c['accent_hover'],
                'btn_hover_border': c['accent_hover'],
                'btn_pressed_bg': c['accent_hover'],
                'close_text': c['muted'],
                'close_hover_bg': 'rgba(0, 0, 0, 0.05)',
                'close_hover_text': c['fg'],
            }
        else:  # dark
            return {
                'panel_bg': 'rgba(30, 30, 46, 0.92)',
                'panel_border': 'rgba(255, 255, 255, 0.08)',
                'edit_bg': 'rgba(39, 39, 42, 0.80)',
                'edit_border': 'rgba(255, 255, 255, 0.06)',
                'edit_focus_border': c['accent'],
                'edit_text': '#e2e2e8',
                'edit_placeholder': c['muted'],
                'edit_selection': 'rgba(250, 250, 250, 0.08)',
                'scrollbar_bg': c['scrollbar_bg'],
                'scrollbar_handle': c['scrollbar_handle'],
                **status_colors,
                'prompt_text': c['muted'],
                'btn_bg': '#ffffff',
                'btn_border': '#ffffff',
                'btn_text': '#1e1e2e',
                'btn_hover_bg': '#e4e4e7',
                'btn_hover_border': '#e4e4e7',
                'btn_pressed_bg': '#d4d4d8',
                'close_text': 'rgba(255, 255, 255, 0.4)',
                'close_hover_bg': 'rgba(255, 255, 255, 0.08)',
                'close_hover_text': 'rgba(255, 255, 255, 0.8)',
            }

    def _apply_theme(self, theme: str):
        """应用指定主题的样式到所有组件。"""
        self._theme = theme
        styles = self._get_theme_styles(theme)

        # 面板容器
        self.container.setStyleSheet(f"""
            #panel {{
                background: {styles['panel_bg']};
                border: 1px solid {styles['panel_border']};
                border-radius: 12px;
            }}
        """)

        # 状态点（保持当前状态颜色）
        self._refresh_status_style()

        # 文本编辑区
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                color: {styles['edit_text']};
                font-size: 14px;
                selection-background-color: {styles['edit_selection']};
            }}
            QScrollBar:vertical {{
                background: {styles['scrollbar_bg']};
                width: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {styles['scrollbar_handle']};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # Prompt 标签
        self.prompt_label.setStyleSheet(f"""
            #promptLabel {{
                color: {styles['prompt_text']};
                font-size: 12px;
            }}
        """)

        # 应用按钮
        self.apply_btn.setStyleSheet(f"""
            #applyBtn {{
                background: {styles['btn_bg']};
                color: {styles['btn_text']};
                border: 1px solid {styles['btn_border']};
                border-radius: 6px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            #applyBtn:hover {{
                background: {styles['btn_hover_bg']};
                color: {styles['btn_text']};
                border: 1px solid {styles['btn_hover_border']};
            }}
            #applyBtn:pressed {{
                background: {styles['btn_pressed_bg']};
            }}
        """)

        # 关闭按钮
        self.close_btn.setStyleSheet(f"""
            #closeBtn {{
                background: transparent;
                border: none;
                font-size: 14px;
                color: {styles['close_text']};
                border-radius: 6px;
            }}
            #closeBtn:hover {{
                background: {styles['close_hover_bg']};
                color: {styles['close_hover_text']};
            }}
        """)

        # Titlebar border
        titlebar = self.container.findChild(QWidget, 'previewTitlebar')
        if titlebar:
            titlebar.setStyleSheet(f"""
                QWidget#previewTitlebar {{
                    border-bottom: 1px solid {styles['panel_border']};
                    background: transparent;
                }}
            """)

        # 页脚分隔线
        footer = self.container.findChild(QWidget, 'previewFooter')
        if footer:
            border_color = styles.get('panel_border', 'rgba(255,255,255,0.06)')
            footer.setStyleSheet(f"""
                QWidget#previewFooter {{
                    border-top: 1px solid {border_color};
                    background: transparent;
                }}
            """)

    def _refresh_status_style(self):
        """根据当前状态刷新状态点样式。"""
        status = self.status_label.text()
        styles = self._get_theme_styles(self._theme)

        color_map = {
            "等待处理": styles['status_waiting'],
            "处理中…": styles['status_processing'],
            "处理完成": styles['status_done'],
            "处理失败": styles['status_failed'],
            "已应用": styles['status_applied'],
        }
        color = color_map.get(status, styles['status_waiting'])

        self.status_dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.status_label.setStyleSheet(f"""
            #statusLabel {{
                color: {color};
                font-size: 12px;
                font-weight: 500;
            }}
        """)

    def set_theme(self, theme: str):
        """公共方法：动态切换主题。"""
        self._apply_theme(theme)

    # ================================================================
    #  UI 构建
    # ================================================================

    def _create_ui(self):
        # --- 外层容器：提供边框拖动区域 ---
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- 内容容器（带内边距的圆角面板） ---
        self.container = QWidget()
        self.container.setObjectName("panel")
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === 顶部栏：可拖动区域 + 状态 + 关闭按钮 ===
        titlebar = QWidget()
        titlebar.setObjectName("previewTitlebar")
        titlebar.setFixedHeight(36)
        top_bar = QHBoxLayout(titlebar)
        top_bar.setContentsMargins(12, 0, 12, 0)
        top_bar.setSpacing(6)

        # 状态指示点
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(12)
        top_bar.addWidget(self.status_dot)

        # 状态文字
        self.status_label = QLabel("等待处理")
        self.status_label.setObjectName("statusLabel")
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()

        # 关闭按钮
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)

        layout.addWidget(titlebar)

        # === 文本编辑区 ===
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(0)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("等待 LLM 处理结果…")
        self.text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body_layout.addWidget(self.text_edit, stretch=1)
        layout.addWidget(body, stretch=1)

        # === 底部栏：prompt 名称 + 应用按钮 ===
        footer = QWidget()
        footer.setObjectName("previewFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        footer_layout.setSpacing(8)

        # Prompt 名称
        self.prompt_label = QLabel("")
        self.prompt_label.setObjectName("promptLabel")
        footer_layout.addWidget(self.prompt_label)
        footer_layout.addStretch()

        # 应用按钮
        self.apply_btn = QPushButton("应用到剪贴板")
        self.apply_btn.setObjectName("applyBtn")
        self.apply_btn.setFixedHeight(30)
        self.apply_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        footer_layout.addWidget(self.apply_btn)

        layout.addWidget(footer)

        outer.addWidget(self.container)

    def _get_fallback_bg(self) -> str:
        """返回 Win10 降级时使用的不透明背景色。"""
        if self._theme == 'dark':
            return '#1e1e2e'
        return '#ffffff'

    def _apply_acrylic_effect(self):
        if sys.platform != 'win32':
            return

        version = sys.getwindowsversion()
        if version.major < 10 or (version.major == 10 and version.build < 22000):
            # Win10 降级：使用不透明背景色
            styles = self._get_theme_styles(self._theme)
            self.container.setStyleSheet(f"""
                #panel {{
                    background: {self._get_fallback_bg()};
                    border: 1px solid {styles['panel_border']};
                    border-radius: 12px;
                }}
            """)
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
            styles = self._get_theme_styles(self._theme)
            self.container.setStyleSheet(f"""
                #panel {{
                    background: {self._get_fallback_bg()};
                    border: 1px solid {styles['panel_border']};
                    border-radius: 12px;
                }}
            """)

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
        self._refresh_status_style()

    def toggle_visibility(self):
        """切换可见性，显示时刷新主题。"""
        if self.isVisible():
            self.hide()
        else:
            # 显示前刷新主题（用户可能在设置中切换了）
            new_theme = self._config.get('preview.theme', 'dark')
            if new_theme != self._theme:
                self._apply_theme(new_theme)
            self.show()
            self.activateWindow()
            self.raise_()

    def showEvent(self, event):
        """每次显示时刷新主题配置。"""
        super().showEvent(event)
        new_theme = self._config.get('preview.theme', 'dark')
        if new_theme != self._theme:
            self._apply_theme(new_theme)

    # ================================================================
    #  拖动 + Resize
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
                self._resize_edge = edge
                self._resize_start_geo = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                return
            else:
                child = self.childAt(pos)
                if child is not self.text_edit and not self.text_edit.isAncestorOf(child):
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_edge and self._resize_start_geo and self._resize_start_pos:
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