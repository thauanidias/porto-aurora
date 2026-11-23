import base64
from io import BytesIO

from PIL import Image


def validate_signature(value: str) -> str:
    if not value:
        return value
    try:
        if not value.startswith("data:image/png;base64,"):
            raise ValueError()
        content = base64.b64decode(value.split(",", 1)[1], validate=True)
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG" or not (10 <= image.width <= 1800 and 10 <= image.height <= 600):
                raise ValueError()
            image.load()
            background = Image.new("RGBA", image.size, "white")
            background.alpha_composite(image.convert("RGBA"))
            if not any(background.convert("L").histogram()[:241]):
                raise ValueError()
    except Exception as exc:
        raise ValueError("Registre uma assinatura válida antes de confirmar a ficha.") from exc
    return value
