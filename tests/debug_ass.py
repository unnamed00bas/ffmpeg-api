"""
Debug ASS style generation
"""

def generate_ass_style(style_dict):
    return (
        f"Style: Default,{style_dict['font_name']},{style_dict['font_size']},"
        f"{style_dict['primary_color']},{style_dict['secondary_color']},"
        f"{style_dict['outline_color']},{style_dict['back_color']},"
        f"{1 if style_dict['bold'] else 0},"
        f"{1 if style_dict['italic'] else 0},"
        f"{1 if style_dict['underline'] else 0},"
        f"{1 if style_dict['strikeout'] else 0},"
        f"{style_dict['scale_x']:.1f},{style_dict['scale_y']:.1f},"
        f"{style_dict['spacing']:.1f},{style_dict['angle']:.1f},"
        f"{style_dict['border_style']},"
        f"{style_dict['outline']:.1f},{style_dict['shadow']:.1f},"
        f"{style_dict['alignment']},"
        f"{style_dict['margin_l']},{style_dict['margin_r']},{style_dict['margin_v']},"
        f"{style_dict['encoding']}"
    )

style = {
    "font_name": "Arial",
    "font_size": 20,
    "primary_color": "&H00FFFFFF",
    "secondary_color": "&H000000FF",
    "outline_color": "&H00000000",
    "back_color": "&H80000000",
    "bold": True,
    "italic": False,
    "underline": False,
    "strikeout": False,
    "scale_x": 1.0,
    "scale_y": 1.0,
    "spacing": 0.0,
    "angle": 0.0,
    "border_style": 1,
    "outline": 2.5,
    "shadow": 3.0,
    "alignment": 2,
    "margin_l": 10,
    "margin_r": 10,
    "margin_v": 10,
    "encoding": 1,
}

ass_style = generate_ass_style(style)
print(ass_style)
