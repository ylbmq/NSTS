import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FIGURES_DIRNAME = "figures"
CONFIDENCE_ACCURACY_CSV = "confidence_accuracy.csv"
CONFIDENCE_ACCURACY_FIGURE = "confidence_accuracy.png"


def _parse_percent(value: str) -> float:
    return float(value.strip().removesuffix("%"))


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def generate_confidence_accuracy_figure(reports_dir: Path) -> Path:
    csv_path = reports_dir / CONFIDENCE_ACCURACY_CSV
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing report: {csv_path}")

    rows = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["Confidence"].lower() == "overall":
                continue
            rows.append({
                "confidence": row["Confidence"],
                "PSR": _parse_percent(row["PSR Accuracy"]),
                "CPE": _parse_percent(row["CPE Accuracy"]),
            })

    if not rows:
        raise ValueError(f"No confidence rows found in {csv_path}")

    width, height = 1800, 1050
    margin_left, margin_right = 210, 110
    margin_top, margin_bottom = 150, 175
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    baseline_y = margin_top + plot_height

    colors = {
        "PSR": (64, 104, 172),
        "CPE": (220, 135, 55),
    }
    background = (255, 255, 255)
    axis_color = (45, 45, 45)
    grid_color = (220, 225, 232)
    text_color = (30, 35, 42)

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    # Adjust these values to change the figure's text size.
    title_font = _load_font(52, bold=True)
    label_font = _load_font(44, bold=True)
    tick_font = _load_font(44)
    value_font = _load_font(44)
    legend_font = _load_font(44)

    title = "Module Accuracy by Confidence State"
    subtitle = "PSR drops under uncertainty; CPE remains comparatively stable."
    title_w, _ = _text_size(draw, title, title_font)
    subtitle_w, _ = _text_size(draw, subtitle, tick_font)
    draw.text(((width - title_w) / 2, 38), title, fill=text_color, font=title_font)
    draw.text(((width - subtitle_w) / 2, 92), subtitle, fill=(90, 95, 105), font=tick_font)

    for tick in range(0, 101, 20):
        y = baseline_y - (tick / 100) * plot_height
        draw.line((margin_left, y, width - margin_right, y), fill=grid_color, width=2)
        tick_text = f"{tick}%"
        tick_w, tick_h = _text_size(draw, tick_text, tick_font)
        draw.text((margin_left - tick_w - 18, y - tick_h / 2), tick_text, fill=text_color, font=tick_font)

    draw.line((margin_left, margin_top, margin_left, baseline_y), fill=axis_color, width=3)
    draw.line((margin_left, baseline_y, width - margin_right, baseline_y), fill=axis_color, width=3)

    horizontal_padding = 120
    usable_plot_width = plot_width - (horizontal_padding * 2)
    x_step = usable_plot_width / (len(rows) - 1)
    x_positions = [margin_left + horizontal_padding + x_step * index for index in range(len(rows))]
    module_order = ["PSR", "CPE"]

    def point_for(index: int, value: float) -> tuple[float, float]:
        return x_positions[index], baseline_y - (value / 100) * plot_height

    close_points = {
        index
        for index, row in enumerate(rows)
        if abs(row["PSR"] - row["CPE"]) < 5
    }

    for module in module_order:
        points = [point_for(index, row[module]) for index, row in enumerate(rows)]
        for start, end in zip(points, points[1:]):
            draw.line((start[0], start[1], end[0], end[1]), fill=colors[module], width=8)
        for index, (x, y) in enumerate(points):
            value = rows[index][module]
            draw.ellipse((x - 14, y - 14, x + 14, y + 14), fill=colors[module], outline=background, width=4)
            value_text = f"{value:.1f}%"
            value_w, value_h = _text_size(draw, value_text, value_font)
            label_y = y - value_h - 34 if module == "PSR" else y + 34
            if index in close_points:
                label_y = y + 34 if module == "PSR" else y - value_h - 34
            if module == "PSR" and label_y < margin_top + 8:
                label_y = y + 22
            if module == "CPE" and y > baseline_y - 70:
                label_y = y - value_h - 18
            draw.text((x - value_w / 2, label_y), value_text, fill=text_color, font=value_font)

    for index, row in enumerate(rows):
        confidence = row["confidence"].capitalize()
        label_w, label_h = _text_size(draw, confidence, label_font)
        draw.text((x_positions[index] - label_w / 2, baseline_y + 28), confidence, fill=text_color, font=label_font)

    y_label = "Accuracy"
    y_label_w, y_label_h = _text_size(draw, y_label, label_font)
    y_label_image = Image.new("RGBA", (y_label_w + 20, y_label_h + 20), (255, 255, 255, 0))
    y_label_draw = ImageDraw.Draw(y_label_image)
    y_label_draw.text((10, 10), y_label, fill=text_color, font=label_font)
    rotated = y_label_image.rotate(90, expand=True)
    image.paste(rotated, (38, margin_top + plot_height // 2 - rotated.height // 2), rotated)

    legend_y = height - 70
    legend_x = margin_left + 460
    for module in module_order:
        line_y = legend_y + 16
        draw.line((legend_x, line_y, legend_x + 52, line_y), fill=colors[module], width=7)
        draw.ellipse((legend_x + 18, line_y - 12, legend_x + 42, line_y + 12), fill=colors[module], outline=background, width=3)
        draw.text((legend_x + 68, legend_y - 2), module, fill=text_color, font=legend_font)
        text_w, _ = _text_size(draw, module, legend_font)
        legend_x += text_w + 190

    figures_dir = reports_dir / FIGURES_DIRNAME
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_path = figures_dir / CONFIDENCE_ACCURACY_FIGURE
    image.save(output_path)
    return output_path


def run_figure_generation(reports_dir: Path) -> None:
    print("\n📈 Starting figure generation...")
    output_path = generate_confidence_accuracy_figure(reports_dir)
    print(f"Saved figure: {output_path}")
    print("\n✅ Figure generation complete.")


if __name__ == "__main__":
    run_figure_generation(Path(__file__).resolve().parent / "data" / "reports")
