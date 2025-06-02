# dashboard/styles.py

COLORS = {
    "background": "#121212",  # Slightly softened dark
    "text": "#E0E0E0",        # Softer white for dark mode
    "primary": "#7C4DFF",     # Vivid purple accent
    "secondary": "#424242",   # For subtle backgrounds
    "card_background": "#1E1E2F",  # Deep slate with blue tint
    "border_color": "rgba(255,255,255,0.08)",  # Soft white border
    "positive_roi_fg": "#00E676",     # Green
    "positive_roi_bg": "rgba(0,230,118,0.1)",
    "negative_roi_fg": "#FF5252",     # Red
    "negative_roi_bg": "rgba(255,82,82,0.1)",
    "warning_roi_fg": "#FFD740",      # Amber
    "warning_roi_bg": "rgba(255,215,64,0.15)",
}

GLOBAL_STYLE = {
    "card": {
        "backgroundColor": COLORS["card_background"],
        "borderColor": COLORS["border_color"],
        "boxShadow": "0 1px 3px rgba(0,0,0,0.3)",
        "transition": "background-color 0.2s ease-in-out",
    },
    "card_body": {
        "padding": "1rem",
        "color": COLORS["text"]
    },
    "list_item": {
        "backgroundColor": COLORS["card_background"],
        "borderColor": COLORS["border_color"],
        "padding": "0.5rem 0.75rem",
        "transition": "background-color 0.2s ease-in-out",
        "cursor": "pointer"
    },
    "divider": {
        "borderColor": COLORS["border_color"],
        "opacity": 0.5
    }
}
