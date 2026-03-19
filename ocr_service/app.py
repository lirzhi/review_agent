from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import pytesseract

app = FastAPI(title="Tesseract OCR Service")


def read_image(file_bytes: bytes):
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr/text")
async def ocr_text(
    file: UploadFile = File(...),
    lang: str = Form("chi_sim+eng"),
    psm: int = Form(6)
):
    content = await file.read()
    img = read_image(content)
    if img is None:
        return JSONResponse(status_code=400, content={"error": "invalid image"})

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    config = f"--oem 1 --psm {psm}"
    text = pytesseract.image_to_string(thr, lang=lang, config=config)

    return {"text": text}


@app.post("/ocr/data")
async def ocr_data(
    file: UploadFile = File(...),
    lang: str = Form("chi_sim+eng"),
    psm: int = Form(6)
):
    content = await file.read()
    img = read_image(content)
    if img is None:
        return JSONResponse(status_code=400, content={"error": "invalid image"})

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    config = f"--oem 1 --psm {psm}"
    data = pytesseract.image_to_data(
        thr,
        lang=lang,
        config=config,
        output_type=pytesseract.Output.DICT
    )

    return {"data": data}