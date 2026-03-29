"""Notion-style SVG icon generator with theme-aware colors."""

from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import Qt, QByteArray

# Notion-style SVG icons (16x16, stroke-based, clean lines)
# Using 'currentColor' placeholder for theme-aware coloring

SVG_ICONS = {
    'settings': '''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="8" cy="8" r="2"/>
  <path d="M8 1v2M8 13v2M1 8h2M13 8h2"/>
  <path d="M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/>
</svg>''',

    'check': '''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 8l3 3 7-7"/>
</svg>''',

    'brain': '''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="8" cy="8" r="5"/>
  <circle cx="8" cy="8" r="2"/>
  <path d="M8 3v2M8 11v2M3 8h2M11 8h2"/>
</svg>''',

    'info': '''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="8" cy="8" r="6"/>
  <path d="M8 7v4M8 5h.01"/>
</svg>''',
}

# Map nav items to icon keys
NAV_ICON_MAP = {
    '通用': 'settings',
    '清洗规则': 'check',
    '大模型': 'brain',
    '关于': 'info',
}


def create_icon_from_svg(svg_data: str, color: str, size: int = 16) -> QIcon:
    """Create QIcon from SVG data with specified color."""
    # Replace 'currentColor' with actual color
    colored_svg = svg_data.replace('currentColor', color)

    # Render SVG to QPixmap
    renderer = QSvgRenderer(QByteArray(colored_svg.encode('utf-8')))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def get_nav_icon(item_name: str, theme: str = 'light', size: int = 16) -> QIcon:
    """Get navigation icon for item name with theme-appropriate color."""
    from ui.styles import ColorPalette

    icon_key = NAV_ICON_MAP.get(item_name)
    if not icon_key:
        return QIcon()

    colors = ColorPalette.get(theme)
    # Use primary text color for icons
    color = colors['text_primary']

    svg_data = SVG_ICONS.get(icon_key, '')
    return create_icon_from_svg(svg_data, color, size)