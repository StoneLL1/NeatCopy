"""Centralized style constants and stylesheet generators for Notion-style UI."""

# Font constants - Notion-inspired system font stack
FONT_FAMILY = '"Segoe UI", "Microsoft YaHei UI", -apple-system, BlinkMacSystemFont, sans-serif'
FONT_SIZE_BASE = '13px'
FONT_SIZE_SMALL = '12px'

# Spacing constants
MARGIN_DIALOG = 16
MARGIN_TAB = 12
SPACING_WIDGETS = 6

# Border radius
RADIUS_SMALL = 4
RADIUS_MEDIUM = 6
RADIUS_LARGE = 8
RADIUS_ROUND = 7


class ColorPalette:
    """Notion-inspired color palettes for light and dark themes."""

    LIGHT = {
        # Backgrounds
        'bg_primary': '#FFFFFF',        # Main background (cards, inputs)
        'bg_secondary': '#F7F7F5',      # Dialog/frame background
        'bg_tertiary': '#FAFAFA',       # Button backgrounds
        'bg_hover': '#F0F0F0',          # Hover states
        'bg_pressed': '#E4E4E4',        # Pressed states
        'bg_selected': '#E8E8E8',       # Selected items
        'bg_groupbox': '#FFFFFF',       # GroupBox background
        'sidebar_bg': '#F7F6F3',        # Sidebar background (Notion-style)
        'sidebar_selected': '#E9E9E9',  # Sidebar selected item bg

        # Borders
        'border_primary': '#E9E9E9',    # Primary borders (subtle)
        'border_secondary': '#EBEBEB',  # GroupBox borders
        'border_input': '#DADADA',      # Input borders
        'border_focus': '#37352F',      # Focus ring (Notion "ink" color)
        'sidebar_border': '#E9E9E9',    # Sidebar right border
        'section_separator': '#E9E9E9', # Section separator line

        # Text
        'text_primary': '#37352F',      # Notion's signature "ink" color
        'text_secondary': '#787774',    # Secondary/placeholder text
        'text_tertiary': '#9B9A97',     # Disabled/hint text
        'text_accent': '#37352F',       # Accent text (status labels)

        # Checkbox
        'checkbox_checked': '#37352F',  # Checkbox checked color
        'checkbox_border': '#BEBEBE',   # Checkbox unchecked border
        'checkbox_border_hover': '#555555',

        # Slider
        'slider_track': '#E0E0E0',      # Slider groove
        'slider_handle': '#FFFFFF',     # Slider handle bg
        'slider_handle_border': '#37352F',
        'slider_active': '#37352F',     # Slider filled portion

        # Scrollbar
        'scrollbar_bg': 'transparent',
        'scrollbar_handle': '#C8C8C8',
        'scrollbar_handle_hover': '#A0A0A0',

        # Buttons
        'save_btn_bg': '#37352F',       # Primary action button
        'save_btn_text': '#FFFFFF',
        'save_btn_hover': '#2F2F2F',
        'reset_btn_bg': '#F7F7F5',
        'reset_btn_border': '#DADADA',

        # Links
        'link_color': '#37352F',
    }

    DARK = {
        # Backgrounds
        'bg_primary': '#191919',        # Notion dark bg
        'bg_secondary': '#1F1F1F',      # Dialog/frame background
        'bg_tertiary': '#2F2F2F',       # Button backgrounds
        'bg_hover': '#373737',          # Hover states
        'bg_pressed': '#404040',        # Pressed states
        'bg_selected': '#2F2F2F',       # Selected items
        'bg_groupbox': '#1F1F1F',       # GroupBox background
        'sidebar_bg': '#202020',        # Sidebar background (Notion-style)
        'sidebar_selected': '#2F2F2F',  # Sidebar selected item bg

        # Borders
        'border_primary': '#37352F',    # Primary borders
        'border_secondary': '#2F2F2F',  # GroupBox borders
        'border_input': '#3D3C3A',      # Input borders
        'border_focus': '#9B9A97',      # Focus ring
        'sidebar_border': '#2F2F2F',    # Sidebar right border
        'section_separator': '#2F2F2F', # Section separator line

        # Text
        'text_primary': '#E9E9E9',      # Primary text
        'text_secondary': '#787774',    # Secondary/placeholder text
        'text_tertiary': '#5A5A5A',     # Disabled/hint text
        'text_accent': '#E9E9E9',       # Accent text

        # Checkbox
        'checkbox_checked': '#E9E9E9',  # Checkbox checked color
        'checkbox_border': '#3D3C3A',
        'checkbox_border_hover': '#787774',

        # Slider
        'slider_track': '#3D3D3D',      # Slider groove
        'slider_handle': '#2F2F2F',     # Slider handle bg
        'slider_handle_border': '#E9E9E9',
        'slider_active': '#787774',     # Slider filled portion

        # Scrollbar
        'scrollbar_bg': 'transparent',
        'scrollbar_handle': '#4A4A4A',
        'scrollbar_handle_hover': '#5A5A5A',

        # Buttons
        'save_btn_bg': '#E9E9E9',       # Primary action button (inverted)
        'save_btn_text': '#191919',
        'save_btn_hover': '#FFFFFF',
        'reset_btn_bg': '#1F1F1F',
        'reset_btn_border': '#3D3C3A',

        # Links
        'link_color': '#E9E9E9',
    }

    @classmethod
    def get(cls, theme: str) -> dict:
        """Return the color palette for the specified theme."""
        return cls.DARK if theme == 'dark' else cls.LIGHT


def get_checkbox_image_path(theme: str) -> str:
    """Return path to check.png for checkbox indicator."""
    # Import here to avoid circular dependency
    from assets import asset
    # For dark theme, we could create a dark_check.png in future
    # For now, use the existing check.png (works reasonably in both themes)
    return asset('check.png').replace('\\', '/')


def get_settings_stylesheet(theme: str) -> str:
    """Generate the main stylesheet for SettingsWindow based on theme."""
    colors = ColorPalette.get(theme)
    check_path = get_checkbox_image_path(theme)

    return f"""
        QDialog {{
            background: {colors['bg_primary']};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_BASE};
            color: {colors['text_primary']};
        }}

        /* 侧边栏分隔线 */
        QFrame#sidebar_separator {{
            background: {colors['sidebar_border']};
            max-width: 1px;
            border: none;
        }}

        /* 底部操作栏 */
        QWidget#bottom_bar {{
            background: {colors['bg_primary']};
            border-top: 1px solid {colors['border_primary']};
        }}

        /* 内容滚动区域 */
        QScrollArea#content_scroll {{
            background: {colors['bg_primary']};
            border: none;
        }}

        /* 内容页面 */
        QWidget#content_page {{
            background: {colors['bg_primary']};
        }}

        /* 页面标题 */
        QLabel#page_title {{
            color: {colors['text_primary']};
            font-family: {FONT_FAMILY};
            font-size: 18px;
            font-weight: bold;
            padding: 0 0 16px 0;
            margin: 0;
            background: transparent;
        }}

        /* 区块分隔线 */
        QFrame#section_separator {{
            background: {colors['section_separator']};
            max-height: 1px;
            border: none;
            margin: 8px 0;
        }}

        /* 热键录制按钮 */
        QPushButton#hotkey_btn {{
            background: {colors['bg_tertiary']};
            border: 1px solid {colors['border_input']};
            border-radius: {RADIUS_MEDIUM}px;
            padding: 4px 12px;
            min-height: 24px;
            min-width: 120px;
            color: {colors['text_primary']};
        }}

        QPushButton#hotkey_btn:hover {{
            background: {colors['bg_hover']};
            border-color: {colors['border_focus']};
        }}

        QPushButton#hotkey_btn:checked {{
            background: {colors['bg_selected']};
            border-color: {colors['text_primary']};
            color: {colors['text_secondary']};
        }}

        /* 主题切换按钮 */
        QPushButton#theme_btn {{
            background: {colors['bg_tertiary']};
            border: 1px solid {colors['border_input']};
            border-radius: {RADIUS_MEDIUM}px;
            padding: 4px 16px;
            min-height: 24px;
            color: {colors['text_primary']};
        }}

        QPushButton#theme_btn:hover {{
            background: {colors['bg_hover']};
        }}

        QPushButton#theme_btn:checked {{
            background: {colors['save_btn_bg']};
            border: none;
            color: {colors['save_btn_text']};
        }}

        /* 次级标签（如滑块说明） */
        QLabel#sub_label {{
            color: {colors['text_secondary']};
            font-size: {FONT_SIZE_SMALL};
            padding: 4px 0;
            background: transparent;
        }}

        /* 传统 TabWidget 样式（保留兼容） */
        QTabWidget::pane {{
            border: 1px solid {colors['border_primary']};
            border-radius: {RADIUS_LARGE}px;
            background: {colors['bg_primary']};
            top: -1px;
        }}

        QTabBar::tab {{
            background: transparent;
            color: {colors['text_secondary']};
            padding: 8px 18px 6px;
            border: none;
            border-bottom: 2px solid transparent;
            font-size: {FONT_SIZE_BASE};
        }}

        QTabBar::tab:selected {{
            color: {colors['text_primary']};
            border-bottom: 2px solid {colors['text_primary']};
            font-weight: bold;
        }}

        QTabBar::tab:hover:!selected {{
            color: {colors['text_secondary']};
            background: {colors['bg_hover']};
            border-radius: {RADIUS_SMALL}px {RADIUS_SMALL}px 0 0;
        }}

        QGroupBox {{
            background: {colors['bg_groupbox']};
            border: 1px solid {colors['border_secondary']};
            border-radius: {RADIUS_LARGE}px;
            margin-top: 12px;
            padding: 14px 12px 10px;
            font-weight: normal;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            top: 2px;
            padding: 0 4px;
            background: {colors['bg_groupbox']};
            color: {colors['text_secondary']};
            font-size: {FONT_SIZE_SMALL};
        }}

        QCheckBox {{
            spacing: 6px;
            font-weight: normal;
            padding: 3px 0;
            color: {colors['text_primary']};
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1.5px solid {colors['checkbox_border']};
            border-radius: {RADIUS_SMALL}px;
            background: {colors['bg_primary']};
        }}

        QCheckBox::indicator:hover {{
            border-color: {colors['checkbox_border_hover']};
        }}

        QCheckBox::indicator:checked {{
            background: {colors['checkbox_checked']};
            border-color: {colors['checkbox_checked']};
            image: url({check_path});
        }}

        QCheckBox::indicator:checked:hover {{
            background: {colors['text_secondary']};
            border-color: {colors['text_secondary']};
        }}

        QPushButton {{
            background: {colors['bg_tertiary']};
            border: 1px solid {colors['border_input']};
            border-radius: {RADIUS_MEDIUM}px;
            padding: 5px 14px;
            min-height: 28px;
            color: {colors['text_primary']};
        }}

        QPushButton:hover {{
            background: {colors['bg_hover']};
            border-color: {colors['border_focus']};
        }}

        QPushButton:pressed {{
            background: {colors['bg_pressed']};
        }}

        QPushButton:checked {{
            background: {colors['bg_selected']};
            border-color: {colors['text_primary']};
            color: {colors['text_primary']};
        }}

        QPushButton#btn_save {{
            background: {colors['save_btn_bg']};
            border: none;
            color: {colors['save_btn_text']};
            font-weight: bold;
            padding: 6px 28px;
            border-radius: {RADIUS_MEDIUM}px;
        }}

        QPushButton#btn_save:hover {{
            background: {colors['save_btn_hover']};
        }}

        QPushButton#btn_reset {{
            background: {colors['reset_btn_bg']};
            border: 1px solid {colors['reset_btn_border']};
            border-radius: {RADIUS_MEDIUM}px;
            padding: 5px 14px;
            min-height: 28px;
            color: {colors['text_primary']};
        }}

        QPushButton#btn_reset:hover {{
            background: {colors['bg_selected']};
            border-color: {colors['border_focus']};
        }}

        QLineEdit {{
            border: 1px solid {colors['border_input']};
            border-radius: {RADIUS_MEDIUM}px;
            padding: 5px 8px;
            background: {colors['bg_primary']};
            selection-background-color: {colors['text_primary']};
            color: {colors['text_primary']};
        }}

        QLineEdit:focus {{
            border: 1.5px solid {colors['border_focus']};
            padding: 4px 7px;
        }}

        QTextEdit {{
            border: 1px solid {colors['border_input']};
            border-radius: {RADIUS_MEDIUM}px;
            padding: 5px;
            background: {colors['bg_primary']};
            color: {colors['text_primary']};
        }}

        QTextEdit:focus {{
            border: 1.5px solid {colors['border_focus']};
            padding: 4px;
        }}

        QListWidget {{
            border: 1px solid {colors['border_input']};
            border-radius: {RADIUS_MEDIUM}px;
            background: {colors['bg_primary']};
            padding: 3px;
            outline: none;
        }}

        QListWidget::item {{
            padding: 5px 8px;
            border-radius: {RADIUS_SMALL}px;
            color: {colors['text_primary']};
        }}

        QListWidget::item:hover {{
            background: {colors['bg_hover']};
        }}

        QListWidget::item:selected {{
            background: {colors['bg_selected']};
            color: {colors['text_primary']};
        }}

        QSlider::groove:horizontal {{
            height: 3px;
            background: {colors['slider_track']};
            border-radius: 1px;
        }}

        QSlider::handle:horizontal {{
            width: 14px;
            height: 14px;
            margin: -5px 0;
            background: {colors['slider_handle']};
            border: 1.5px solid {colors['slider_handle_border']};
            border-radius: {RADIUS_ROUND}px;
        }}

        QSlider::handle:horizontal:hover {{
            background: {colors['bg_hover']};
        }}

        QSlider::handle:horizontal:pressed {{
            background: {colors['slider_active']};
            border-color: {colors['text_secondary']};
        }}

        QSlider::sub-page:horizontal {{
            background: {colors['slider_active']};
            border-radius: 1px;
        }}

        QLabel {{
            background: transparent;
            color: {colors['text_secondary']};
        }}

        QLabel#status_label {{
            color: {colors['text_accent']};
            font-weight: bold;
        }}

        QScrollBar:vertical {{
            width: 5px;
            background: {colors['scrollbar_bg']};
        }}

        QScrollBar::handle:vertical {{
            background: {colors['scrollbar_handle']};
            border-radius: 2px;
            min-height: 24px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {colors['scrollbar_handle_hover']};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            background: none;
        }}

        QMenu {{
            background: {colors['bg_primary']};
            border: 1px solid {colors['border_primary']};
            border-radius: {RADIUS_LARGE}px;
            padding: 4px;
        }}

        QMenu::item {{
            padding: 5px 20px 5px 10px;
            border-radius: {RADIUS_SMALL}px;
        }}

        QMenu::item:selected {{
            background: {colors['bg_hover']};
        }}

        QMenu::item:disabled {{
            color: {colors['text_tertiary']};
        }}

        QToolTip {{
            background: {colors['bg_primary']};
            border: 1px solid {colors['border_primary']};
            border-radius: {RADIUS_SMALL}px;
            padding: 4px 8px;
            color: {colors['text_primary']};
            font-size: {FONT_SIZE_SMALL};
        }}
    """


def get_sidebar_stylesheet(theme: str) -> str:
    """Generate stylesheet for SidebarWidget based on theme."""
    colors = ColorPalette.get(theme)
    indicator_color = '#2383E2'  # Blue indicator bar (consistent across themes)

    return f"""
        QWidget#sidebar {{
            background: {colors['sidebar_bg']};
            border-right: 1px solid {colors['sidebar_border']};
        }}

        QLabel#sidebarAppName {{
            color: {colors['text_secondary']};
            font-family: {FONT_FAMILY};
            font-size: 14px;
            font-weight: bold;
        }}

        QListWidget#sidebarNav {{
            background: transparent;
            border: none;
            outline: none;
            padding: 0;
        }}

        QListWidget#sidebarNav::item {{
            background: transparent;
            color: {colors['text_primary']};
            font-family: {FONT_FAMILY};
            font-size: 13px;
            padding: 8px 20px;
            height: 36px;
            border: none;
            border-left: 3px solid transparent;
        }}

        QListWidget#sidebarNav::item:hover {{
            background: {colors['bg_hover']};
        }}

        QListWidget#sidebarNav::item:selected {{
            background: {colors['sidebar_selected']};
            font-weight: bold;
            border-left: 3px solid {indicator_color};
        }}
    """


def get_content_stylesheet(theme: str) -> str:
    """Generate stylesheet for content area (QScrollArea) based on theme."""
    colors = ColorPalette.get(theme)

    return f"""
        QScrollArea {{
            background: {colors['bg_primary']};
            border: none;
        }}

        QScrollArea > QWidget > QWidget {{
            background: {colors['bg_primary']};
        }}

        QLabel#pageTitle {{
            color: {colors['text_primary']};
            font-family: {FONT_FAMILY};
            font-size: 18px;
            font-weight: bold;
            padding: 0;
            margin: 0;
        }}

        QLabel#sectionTitle {{
            color: {colors['text_secondary']};
            font-family: {FONT_FAMILY};
            font-size: 12px;
            font-weight: normal;
            padding: 8px 0 4px 0;
        }}

        QFrame#sectionSeparator {{
            background: {colors['section_separator']};
            max-height: 1px;
            border: none;
        }}

        QFrame#bottomBar {{
            background: {colors['bg_primary']};
            border-top: 1px solid {colors['border_primary']};
        }}
    """


def get_full_stylesheet(theme: str) -> str:
    """Generate combined stylesheet for all UI elements."""
    return get_settings_stylesheet(theme) + get_sidebar_stylesheet(theme) + get_content_stylesheet(theme)