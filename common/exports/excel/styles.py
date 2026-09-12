"""
Styling definitions for openpyxl Excel workbooks in Bara3im Shoot.
Provides consistent, executive themes (ARDIS Blue, SABLLET Pink, Default Slate/Gold),
typography, borders, number formatting, and row styling.
"""

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# ── Color Palette ─────────────────────────────────────────────────────────────
HEADER_BG_DEFAULT = "1E293B"      # Slate Dark
HEADER_TEXT_DEFAULT = "FFFFFF"

HEADER_BG_ARDIS = "1565C0"        # ARDIS Blue
HEADER_TEXT_ARDIS = "FFFFFF"

HEADER_BG_SABLLET = "D81B60"      # SABLLET Pink/Magenta
HEADER_TEXT_SABLLET = "FFFFFF"

HEADER_BG_GOLD = "D97706"         # Executive Gold
HEADER_TEXT_GOLD = "FFFFFF"

ZEBRA_BG = "F8FAFC"               # Light Gray/Blue for alternate rows
TOTAL_ROW_BG = "F1F5F9"           # Highlight fill for summary totals

BORDER_COLOR = "CBD5E1"           # Soft gray border
TOTAL_BORDER_COLOR = "475569"     # Darker border for totals

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_FAMILY = "Calibri"

FONT_TITLE = Font(name=FONT_FAMILY, size=16, bold=True, color="0F172A")
FONT_SUBTITLE = Font(name=FONT_FAMILY, size=11, italic=True, color="64748B")
FONT_SECTION_HEADER = Font(name=FONT_FAMILY, size=12, bold=True, color="1E293B")

FONT_HEADER = Font(name=FONT_FAMILY, size=11, bold=True, color=HEADER_TEXT_DEFAULT)
FONT_HEADER_ARDIS = Font(name=FONT_FAMILY, size=11, bold=True, color=HEADER_TEXT_ARDIS)
FONT_HEADER_SABLLET = Font(name=FONT_FAMILY, size=11, bold=True, color=HEADER_TEXT_SABLLET)
FONT_HEADER_GOLD = Font(name=FONT_FAMILY, size=11, bold=True, color=HEADER_TEXT_GOLD)

FONT_BODY = Font(name=FONT_FAMILY, size=10, color="1E293B")
FONT_BODY_BOLD = Font(name=FONT_FAMILY, size=10, bold=True, color="1E293B")
FONT_TOTAL = Font(name=FONT_FAMILY, size=11, bold=True, color="0F172A")

# ── Fills ─────────────────────────────────────────────────────────────────────
FILL_HEADER_DEFAULT = PatternFill(start_color=HEADER_BG_DEFAULT, end_color=HEADER_BG_DEFAULT, fill_type="solid")
FILL_HEADER_ARDIS = PatternFill(start_color=HEADER_BG_ARDIS, end_color=HEADER_BG_ARDIS, fill_type="solid")
FILL_HEADER_SABLLET = PatternFill(start_color=HEADER_BG_SABLLET, end_color=HEADER_BG_SABLLET, fill_type="solid")
FILL_HEADER_GOLD = PatternFill(start_color=HEADER_BG_GOLD, end_color=HEADER_BG_GOLD, fill_type="solid")

FILL_ZEBRA = PatternFill(start_color=ZEBRA_BG, end_color=ZEBRA_BG, fill_type="solid")
FILL_TOTAL = PatternFill(start_color=TOTAL_ROW_BG, end_color=TOTAL_ROW_BG, fill_type="solid")

# Status pills fills
FILL_GREEN = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
FONT_GREEN = Font(name=FONT_FAMILY, size=10, bold=True, color="166534")

FILL_RED = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
FONT_RED = Font(name=FONT_FAMILY, size=10, bold=True, color="991B1B")

FILL_AMBER = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
FONT_AMBER = Font(name=FONT_FAMILY, size=10, bold=True, color="92400E")

# ── Alignments ────────────────────────────────────────────────────────────────
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")

ALIGN_HEADER_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_HEADER_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_HEADER_RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)

# ── Borders ───────────────────────────────────────────────────────────────────
THIN_SIDE = Side(border_style="thin", color=BORDER_COLOR)
DOUBLE_BOTTOM_SIDE = Side(border_style="double", color=TOTAL_BORDER_COLOR)
THICK_TOP_SIDE = Side(border_style="thin", color=TOTAL_BORDER_COLOR)

BORDER_CELL = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
BORDER_TOTAL = Border(top=THICK_TOP_SIDE, bottom=DOUBLE_BOTTOM_SIDE, left=THIN_SIDE, right=THIN_SIDE)

# ── Number Format Strings ─────────────────────────────────────────────────────
FMT_CURRENCY = '#,##0.00 "DA"'
FMT_INTEGER = '#,##0'
FMT_DECIMAL = '#,##0.00'
FMT_PERCENTAGE = '0.0%'
FMT_DATE = 'YYYY-MM-DD'
FMT_TIME = 'HH:MM'
