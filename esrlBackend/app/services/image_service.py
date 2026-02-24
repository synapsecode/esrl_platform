from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import pytesseract

_processor = None
_model = None


def _get_model():
    global _processor, _model
    if _processor is None or _model is None:
        _processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        _model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return _processor, _model


def generate_caption(image_path: str) -> str:
    processor, model = _get_model()
    image = Image.open(image_path).convert("RGB")
    inputs = processor(image, return_tensors="pt")
    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption


def extract_text(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")
    return pytesseract.image_to_string(image).strip()
