import base64
import io

from PIL import Image, ImageDraw


def consent_signature():
    image = Image.new("RGB", (900, 220), "white")
    ImageDraw.Draw(image).line((30, 120, 250, 50, 450, 140), fill="black", width=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
