import os
import tempfile
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальный конвертер: модели загружаются ОДИН РАЗ при старте
# Это экономит ~3-5 сек на каждый запрос
converter = DocumentConverter(
    pipeline_options=PdfPipelineOptions(
        do_ocr=True,              # Включить OCR для сканов
        do_table_structure=True,  # Распознавать таблицы
        # table_mode="accurate",  # или "fast" (по умолчанию accurate)
    )
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("✅ Docling models loaded. Service ready.")
    yield
    logger.info("🛑 Service shutting down.")

app = FastAPI(title="Docling Parser Microservice", version="1.0.0", lifespan=lifespan)

@app.post("/api/v1/convert")
async def convert_document(
    file: UploadFile = File(...),
    output_format: str = Form("markdown"),
    max_file_mb: int = Form(50)
):
    MAX_MB = 50
    max_file_mb = max(1, min(max_file_mb, MAX_MB))
    ALLOWED = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
    # 1. Валидация
    if not file.content_type.startswith(("application/pdf", "application/vnd.openxmlformats", "image/", "text/html")):
        raise HTTPException(400, "Unsupported file type")

    # Читаем файл в память
    content = await file.read(max_file_mb * 1024 * 1024 + 1)  # не читаем больше лимита
    if len(content) > max_file_mb * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {max_file_mb}MB limit")

    # 2. Сохраняем во временный файл (Docling работает с файловыми путями)
    ext = os.path.splitext(file.filename or ".pdf")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "Unsupported file extension")
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 3. Парсинг
        result = converter.convert(tmp_path)

        # 4. Экспорт
        if output_format == "markdown":
            payload = result.document.export_to_markdown()
        elif output_format == "json":
            payload = result.document.export_to_dict()
        else:
            raise HTTPException(400, "output_format must be 'markdown' or 'json'")

        # 5. Ответ для C#
        return JSONResponse(content={
            "status": "success",
            "filename": file.filename,
            "output_format": output_format,
            "content": payload,
            "metadata": {
                "pages_processed": len(result.document.pages),
                "tables_detected": result.document.num_tables,
                "ocr_applied": result.pipeline_options.do_ocr
            }
        })

    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        raise HTTPException(500, "Processing error")
    finally:
        # 6. Чистим временный файл
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "docling-parser"}

if __name__ == "__main__":
    import uvicorn
    # workers=1: модели занимают много RAM, лучше масштабировать контейнеры
    uvicorn.run(app, host="127.0.0.1", port=5001, workers=1)