"""Shadcn-inspired design tokens and stylesheet generators for NeatCopy UI."""

# Font stacks
FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", sans-serif'
FONT_MONO = '"Cascadia Code", "Fira Code", Consolas, monospace'

# Font sizes
FONT_SIZE_XS = '12px'
FONT_SIZE_SM = '14px'
FONT_SIZE_BASE = '16px'

# Border radius
RADIUS_SM = '6px'
RADIUS_MD = '8px'
RADIUS_LG = '12px'
RADIUS_PILL = '9999px'


class ColorPalette:
    """Shadcn-inspired color palettes using zinc + black CTA."""

    LIGHT = {
        # Backgrounds
        'bg':               '#ffffff',
        'surface_alt':      '#f9fafb',
        'fg':               '#111827',
        'fg_2':             '#334155',
        'muted':            '#64748b',

        # Soft overlays
        'fg_soft':          'rgba(17,24,39,0.05)',
        'border':           '#e5e7eb',
        'border_strong':    '#cbd5e1',

        # Accent (CTA)
        'accent':           '#000000',
        'accent_on':        '#ffffff',
        'accent_hover':     '#1a1a1a',
        'accent_soft':      'rgba(0,0,0,0.08)',

        # Semantic colors
        'success':          '#16a34a',
        'success_soft':     'rgba(22,163,74,0.10)',
        'warn':             '#d97706',
        'warn_soft':        'rgba(217,119,6,0.10)',
        'danger':           '#dc2626',
        'danger_soft':      'rgba(220,38,38,0.10)',
        'info':             '#3b82f6',
        'info_soft':        'rgba(59,130,246,0.10)',

        # Scrollbar
        'scrollbar_bg':         'transparent',
        'scrollbar_handle':     '#cbd5e1',
        'scrollbar_handle_hover': '#94a3b8',
    }

    DARK = {
        # Backgrounds
        'bg':               '#18181b',
        'surface_alt':      '#27272a',
        'fg':               '#fafafa',
        'fg_2':             '#d4d4d8',
        'muted':            '#a1a1aa',

        # Soft overlays
        'fg_soft':          'rgba(250,250,250,0.05)',
        'border':           '#3f3f46',
        'border_strong':    '#52525b',

        # Accent (CTA)
        'accent':           '#fafafa',
        'accent_on':        '#18181b',
        'accent_hover':     '#e4e4e7',
        'accent_soft':      'rgba(250,250,250,0.08)',

        # Semantic colors
        'success':          '#4ade80',
        'success_soft':     'rgba(74,222,128,0.10)',
        'warn':             '#fbbf24',
        'warn_soft':        'rgba(251,191,36,0.10)',
        'danger':           '#f87171',
        'danger_soft':      'rgba(248,113,113,0.10)',
        'info':             '#60a5fa',
        'info_soft':        'rgba(96,165,250,0.10)',

        # Scrollbar
        'scrollbar_bg':         'transparent',
        'scrollbar_handle':     '#52525b',
        'scrollbar_handle_hover': '#71717a',
    }

    @classmethod
    def get(cls, theme: str) -> dict:
        """Return the color palette for the specified theme."""
        return cls.DARK if theme == 'dark' else cls.LIGHT


def get_checkbox_image_path(theme: str) -> str:
    """Return path to check image for checkbox indicator."""
    from assets import asset
    if theme == 'dark':
        return asset('check_white.png').replace('\\', '/')
    return asset('check.png').replace('\\', '/')


def get_settings_stylesheet(theme: str) -> str:
    """Generate the main stylesheet for SettingsWindow based on theme."""
    c = ColorPalette.get(theme)
    check_path = get_checkbox_image_path(theme)

    return f"""
        /* ── Dialog ── */
        QDialog {{
            background: {c['bg']};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_SM};
            color: {c['fg']};
        }}

        /* ── Content area ── */
        QScrollArea#content_scroll {{
            background: {c['bg']};
            border: none;
        }}

        QWidget#content_page {{
            background: {c['bg']};
        }}

        /* ── Layout dividers ── */
        QFrame#sidebar_separator {{
            background: {c['bg']};
            max-width: 1px;
            border: none;
        }}

        QWidget#bottom_bar {{
            background: {c['bg']};
            border-top: 1px solid {c['border']};
        }}

        /* ── Page title ── */
        QLabel#page_title {{
            color: {c['fg']};
            font-family: {FONT_FAMILY};
            font-size: 18px;
            font-weight: bold;
            padding: 0 0 16px 0;
            margin: 0;
            background: transparent;
        }}

        /* ── Section separator ── */
        QFrame#section_separator {{
            background: {c['border']};
            max-height: 1px;
            border: none;
            margin: 8px 0;
        }}

        /* ── Hotkey record button ── */
        QPushButton#hotkey_btn {{
            background: {c['surface_alt']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 4px 12px;
            min-height: 24px;
            min-width: 100px;
            color: {c['muted']};
            font-family: {FONT_MONO};
            font-size: {FONT_SIZE_XS};
        }}

        QPushButton#hotkey_btn:hover {{
            border-color: {c['border_strong']};
        }}

        QPushButton#hotkey_btn:checked {{
            background: {c['accent_soft']};
            border-color: {c['accent']};
            color: {c['accent']};
        }}

        /* ── Theme toggle button (legacy, kept for compat) ── */
        QPushButton#theme_btn {{
            background: {c['surface_alt']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_MD};
            padding: 4px 16px;
            min-height: 24px;
            color: {c['fg']};
        }}

        QPushButton#theme_btn:hover {{
            background: {c['fg_soft']};
        }}

        QPushButton#theme_btn:checked {{
            background: {c['accent']};
            border: none;
            color: {c['accent_on']};
        }}

        /* ── Sub label ── */
        QLabel#sub_label {{
            color: {c['muted']};
            font-size: {FONT_SIZE_XS};
            padding: 4px 0;
            background: transparent;
        }}

        /* ── GroupBox ── */
        QGroupBox {{
            background: {c['bg']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_LG};
            margin-top: 16px;
            padding: 18px 12px 12px;
            font-weight: normal;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            top: 0px;
            padding: 0 6px;
            background: {c['bg']};
            color: {c['fg']};
            font-size: 15px;
            font-weight: bold;
        }}

        /* ── Checkbox ── */
        QCheckBox {{
            spacing: 6px;
            font-weight: normal;
            padding: 3px 0;
            color: {c['fg']};
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1.5px solid {c['border_strong']};
            border-radius: {RADIUS_SM};
            background: {c['bg']};
        }}

        QCheckBox::indicator:checked {{
            background: {c['accent']};
            border-color: {c['accent']};
            image: url({check_path});
        }}

        /* ── Generic push buttons ── */
        QPushButton {{
            background: {c['surface_alt']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 4px 12px;
            min-height: 24px;
            color: {c['fg']};
            font-size: {FONT_SIZE_XS};
            font-weight: 500;
        }}

        QPushButton:hover {{
            border-color: {c['border_strong']};
            background: {c['fg_soft']};
        }}

        QPushButton:pressed {{
            background: {c['border']};
        }}

        /* ── Save (primary CTA) ── */
        QPushButton#btn_save {{
            background: {c['accent']};
            border: none;
            color: {c['accent_on']};
            font-weight: 500;
            font-size: {FONT_SIZE_XS};
            padding: 4px 12px;
            border-radius: {RADIUS_SM};
        }}

        QPushButton#btn_save:hover {{
            background: {c['accent_hover']};
        }}

        /* ── Reset button ── */
        QPushButton#btn_reset {{
            background: {c['bg']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 4px 12px;
            min-height: 24px;
            color: {c['fg']};
            font-size: {FONT_SIZE_XS};
        }}

        QPushButton#btn_reset:hover {{
            background: {c['accent_soft']};
            border-color: {c['border_strong']};
        }}

        /* ── Input fields ── */
        QLineEdit {{
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 8px 12px;
            background: {c['bg']};
            selection-background-color: {c['accent']};
            color: {c['fg']};
        }}

        QLineEdit:focus {{
            border: 1px solid {c['accent']};
            padding: 8px 12px;
        }}

        QTextEdit {{
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 8px 12px;
            background: {c['bg']};
            color: {c['fg']};
        }}

        QTextEdit:focus {{
            border: 1px solid {c['accent']};
            padding: 8px 12px;
        }}

        /* ── List widgets ── */
        QListWidget {{
            border: 1px solid {c['border']};
            border-radius: {RADIUS_MD};
            background: {c['bg']};
            padding: 3px;
            outline: none;
        }}

        QListWidget::item {{
            padding: 5px 8px;
            border-radius: {RADIUS_SM};
            color: {c['fg']};
        }}

        QListWidget::item:hover {{
            background: {c['fg_soft']};
        }}

        QListWidget::item:selected {{
            background: {c['accent_soft']};
            color: {c['fg']};
        }}

        /* ── Slider ── */
        QSlider::groove:horizontal {{
            height: 4px;
            background: {c['border']};
            border-radius: 2px;
        }}

        QSlider::handle:horizontal {{
            width: 16px;
            height: 16px;
            margin: -6px 0;
            background: #ffffff;
            border: 2px solid {c['accent']};
            border-radius: 8px;
        }}

        QSlider::sub-page:horizontal {{
            background: {c['accent']};
            border-radius: 2px;
        }}

        /* ── Labels ── */
        QLabel {{
            background: transparent;
            color: {c['muted']};
        }}

        QLabel#status_label {{
            color: {c['fg']};
            font-weight: bold;
        }}

        /* ── Scrollbar ── */
        QScrollBar:vertical {{
            width: 4px;
            background: {c['scrollbar_bg']};
        }}

        QScrollBar::handle:vertical {{
            background: {c['scrollbar_handle']};
            border-radius: 2px;
            min-height: 24px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {c['scrollbar_handle_hover']};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            background: none;
        }}

        /* ── Menu ── */
        QMenu {{
            background: {c['bg']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_MD};
            padding: 4px 0;
        }}

        QMenu::item {{
            padding: 8px 12px;
            border-radius: {RADIUS_SM};
        }}

        QMenu::item:selected {{
            background: {c['accent_soft']};
        }}

        QMenu::item:disabled {{
            color: {c['muted']};
        }}

        /* ── Tooltip ── */
        QToolTip {{
            background: {c['bg']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 4px 8px;
            color: {c['fg']};
            font-size: {FONT_SIZE_XS};
        }}
    """


def get_sidebar_stylesheet(theme: str) -> str:
    """Generate stylesheet for SidebarWidget based on theme."""
    c = ColorPalette.get(theme)

    return f"""
        QWidget#sidebar {{
            background: {c['bg']};
            border-right: 1px solid {c['border']};
        }}

        QLabel#sidebarAppName {{
            color: {c['fg_2']};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_BASE};
            font-weight: bold;
            letter-spacing: -0.02em;
        }}

        QListWidget#sidebarNav {{
            background: transparent;
            border: none;
            outline: none;
            padding: 0;
        }}

        QListWidget#sidebarNav::item {{
            background: transparent;
            color: {c['muted']};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_SM};
            font-weight: normal;
            padding: 8px 16px 8px 19px;
            height: 36px;
            border: none;
            border-left: 3px solid transparent;
        }}

        QListWidget#sidebarNav::item:hover {{
            background: {c['fg_soft']};
            color: {c['fg']};
        }}

        QListWidget#sidebarNav::item:selected {{
            background: {c['accent_soft']};
            border-left: 3px solid {c['accent']};
            color: {c['fg']};
            font-weight: 500;
        }}
    """


def get_history_stylesheet(theme: str) -> str:
    """Generate stylesheet for HistoryWindow based on theme."""
    c = ColorPalette.get(theme)
    check_path = get_checkbox_image_path(theme)

    return f"""
        /* ── Dialog ── */
        QDialog {{
            background: {c['bg']};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_SM};
            color: {c['fg']};
        }}

        /* ── Main panel ── */
        QWidget#panel {{
            background: {c['bg']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_LG};
        }}

        /* ── Title bar ── */
        QWidget#titlebar {{
            background: {c['bg']};
            border-bottom: 1px solid {c['border']};
        }}

        /* ── Toolbar ── */
        QWidget#toolbar {{
            background: {c['bg']};
            border-bottom: 1px solid {c['border']};
        }}

        /* ── List widgets ── */
        QListWidget {{
            background: transparent;
            border: none;
            outline: none;
            padding: 0;
        }}

        QListWidget::item {{
            padding: 8px 12px;
            border-bottom: 1px solid {c['border']};
            color: {c['fg']};
        }}

        QListWidget::item:hover {{
            background: {c['fg_soft']};
        }}

        QListWidget::item:selected {{
            background: {c['accent_soft']};
            color: {c['fg']};
        }}

        /* ── Input fields ── */
        QLineEdit {{
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 8px 12px;
            background: {c['bg']};
            selection-background-color: {c['accent']};
            color: {c['fg']};
        }}

        QLineEdit:focus {{
            border: 1px solid {c['accent']};
            padding: 8px 12px;
        }}

        QTextEdit {{
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 8px 12px;
            background: {c['bg']};
            color: {c['fg']};
        }}

        QTextEdit:focus {{
            border: 1px solid {c['accent']};
            padding: 8px 12px;
        }}

        /* ── Buttons ── */
        QPushButton {{
            background: {c['surface_alt']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 4px 12px;
            min-height: 24px;
            color: {c['fg']};
            font-size: {FONT_SIZE_XS};
            font-weight: 500;
        }}

        QPushButton:hover {{
            border-color: {c['border_strong']};
            background: {c['fg_soft']};
        }}

        QPushButton:pressed {{
            background: {c['border']};
        }}

        QPushButton#btn_copy {{
            background: {c['accent']};
            border: none;
            color: {c['accent_on']};
            font-weight: 500;
            padding: 4px 12px;
            font-size: {FONT_SIZE_XS};
            border-radius: {RADIUS_SM};
        }}

        QPushButton#btn_copy:hover {{
            background: {c['accent_hover']};
        }}

        QPushButton#btn_delete {{
            background: transparent;
            border: 1px solid {c['border']};
            color: {c['danger']};
            border-radius: {RADIUS_SM};
            padding: 4px 12px;
            font-size: {FONT_SIZE_XS};
        }}

        QPushButton#btn_delete:hover {{
            background: {c['danger_soft']};
            border-color: {c['danger']};
        }}

        /* ── Labels ── */
        QLabel {{
            background: transparent;
            color: {c['muted']};
        }}

        QLabel#detail_label {{
            color: {c['fg']};
            font-weight: bold;
        }}

        /* ── Scrollbar ── */
        QScrollBar:vertical {{
            width: 4px;
            background: {c['scrollbar_bg']};
        }}

        QScrollBar::handle:vertical {{
            background: {c['scrollbar_handle']};
            border-radius: 2px;
            min-height: 24px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {c['scrollbar_handle_hover']};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            background: none;
        }}

        /* ── Search input ── */
        QLineEdit#search_input {{
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM};
            padding: 6px 10px;
            background: {c['surface_alt']};
            color: {c['fg']};
        }}

        QLineEdit#search_input:focus {{
            border: 1px solid {c['accent']};
            padding: 6px 10px;
        }}

        /* ── Status label ── */
        QLabel#status_label {{
            color: {c['fg']};
            font-weight: bold;
        }}

        /* ── Mode badge ── */
        QLabel#mode_badge {{
            background: {c['accent_soft']};
            color: {c['accent']};
            border-radius: {RADIUS_PILL};
            padding: 2px 8px;
            font-size: {FONT_SIZE_XS};
            font-weight: bold;
        }}
    """
