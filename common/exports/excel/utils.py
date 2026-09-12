"""
Utility functions for Excel generation, sheet name sanitization,
filename formatting, and auto-column layout in openpyxl.
"""

import re
from datetime import date, datetime
from openpyxl.utils import get_column_letter


FORBIDDEN_SHEET_CHARS = re.compile(r'[\[\]:*?/\\]')


def sanitize_sheet_name(name: str, existing_names: set = None) -> str:
    """
    Sanitizes sheet names to respect Excel constraints:
    1. Maximum 31 characters.
    2. No forbidden characters: [ ] : * ? / \
    3. Handles duplicate names by appending (1), (2), etc.
    """
    if not name:
        name = "Sheet"
    
    # Remove forbidden characters
    clean = FORBIDDEN_SHEET_CHARS.sub('', str(name)).strip()
    if not clean:
        clean = "Sheet"

    # Truncate to max 31 chars
    clean = clean[:31].strip()

    if existing_names is None:
        return clean

    # Ensure uniqueness
    if clean not in existing_names:
        existing_names.add(clean)
        return clean

    counter = 1
    while True:
        suffix = f" ({counter})"
        truncated_base = clean[: 31 - len(suffix)].strip()
        candidate = f"{truncated_base}{suffix}"
        if candidate not in existing_names:
            existing_names.add(candidate)
            return candidate
        counter += 1


def generate_export_filename(prefix: str = "Bara3im_Shoot", subject: str = "Report", start_date=None, end_date=None) -> str:
    """
    Generates standardized, clean filenames for exports.
    Examples:
    - Bara3im_Shoot_Employee_Ahmed_2026-09-12.xlsx
    - Bara3im_Shoot_ARDIS_2026-09-01_to_2026-09-12.xlsx
    """
    clean_subj = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(subject)).strip('_')
    clean_subj = re.sub(r'_+', '_', clean_subj)

    today_str = date.today().strftime('%Y-%m-%d')

    if start_date and end_date and str(start_date) != str(end_date):
        s_str = start_date.strftime('%Y-%m-%d') if isinstance(start_date, (date, datetime)) else str(start_date)
        e_str = end_date.strftime('%Y-%m-%d') if isinstance(end_date, (date, datetime)) else str(end_date)
        date_part = f"{s_str}_to_{e_str}"
    elif start_date:
        date_part = start_date.strftime('%Y-%m-%d') if isinstance(start_date, (date, datetime)) else str(start_date)
    else:
        date_part = today_str

    filename = f"{prefix}_{clean_subj}_{date_part}.xlsx"
    return re.sub(r'_+', '_', filename)


def auto_fit_columns(ws, min_width: int = 12, max_width: int = 45):
    """
    Calculates cell content lengths and adjusts worksheet column widths.
    """
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        
        for cell in col:
            val = cell.value
            if val is not None:
                # Handle line breaks in headers or strings
                lines = str(val).split('\n')
                for line in lines:
                    max_len = max(max_len, len(line))
        
        # Add padding
        calculated_width = max(max_len + 4, min_width)
        ws.column_dimensions[col_letter].width = min(calculated_width, max_width)
