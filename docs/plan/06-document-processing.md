# 06 — Pipeline de Procesamiento de Documentos

## 1. Tipos de documentos aceptados

| Tipo | Formatos | Ejemplo |
|------|---------|---------|
| Resultados de laboratorio | PDF, imagen (JPG/PNG), DOCX | Hemograma, química sanguínea |
| Recetas médicas | PDF, imagen | Prescripción de medicamentos |
| Informes médicos | PDF, DOCX | Alta hospitalaria, informe de consulta |
| Imágenes médicas no-diagnósticas | JPG, PNG | Foto de lesión cutánea, erupciones |
| Documentos escaneados | PDF (escaneado), imagen | Cualquier documento médico escaneado |
| Resultados de estudios | PDF | Ecografías, radiografías (informe, no la imagen DICOM) |

### Formatos NO soportados (MVP)
- DICOM (imágenes diagnósticas reales) — requiere infraestructura especializada
- HL7/FHIR — estándar de interoperabilidad, futuro
- Archivos >20MB

## 2. Pipeline completo

```
┌─────────────┐
│   UPLOAD     │  Usuario sube archivo desde el chat
└──────┬──────┘
       │
┌──────▼──────┐
│  VALIDACIÓN  │  Formato, tamaño, tipo MIME, virus scan
└──────┬──────┘
       │
┌──────▼──────┐
│  ALMACENAJE  │  S3/MinIO + metadata en PostgreSQL
└──────┬──────┘
       │
┌──────▼──────────────┐
│  CLASIFICACIÓN       │  ¿Es lab? ¿Receta? ¿Informe? ¿Imagen?
└──────┬──────────────┘
       │
       ├─── PDF legible ──▶ Extracción directa de texto
       │
       ├─── PDF escaneado ──▶ OCR ──▶ Texto
       │
       ├─── Imagen ──▶ OCR (si tiene texto) ──▶ Texto
       │                └──▶ Análisis visual (si es lesión)
       │
       └─── DOCX ──▶ Extracción directa de texto
              │
┌─────────────▼─────────────┐
│  EXTRACCIÓN DE DATOS       │  NER médico: valores, fechas, medicamentos
│  CLÍNICOS ESTRUCTURADOS    │  
└─────────────┬─────────────┘
              │
┌─────────────▼─────────────┐
│  GENERACIÓN DE EMBEDDING   │  Vector para búsqueda semántica
└─────────────┬─────────────┘
              │
┌─────────────▼─────────────┐
│  VINCULACIÓN AL CASO       │  Se asocia al caso activo
└─────────────┬─────────────┘
              │
┌─────────────▼─────────────┐
│  DISPONIBLE PARA AGENTES   │  Los agentes pueden consultar el documento
└───────────────────────────┘
```

## 3. Validación de upload

```python
class DocumentValidator:
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
    
    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".docx"}
    
    async def validate(self, file: UploadFile) -> ValidationResult:
        errors = []
        
        # 1. Extensión
        ext = Path(file.filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            errors.append(f"Formato no soportado: {ext}")
        
        # 2. MIME type
        mime = magic.from_buffer(await file.read(1024), mime=True)
        await file.seek(0)
        if mime not in self.ALLOWED_MIME_TYPES:
            errors.append(f"Tipo MIME no permitido: {mime}")
        
        # 3. Tamaño
        content = await file.read()
        await file.seek(0)
        if len(content) > self.MAX_FILE_SIZE:
            errors.append(f"Archivo demasiado grande: {len(content)} bytes")
        
        # 4. Integridad (no corrupto)
        if ext == ".pdf":
            if not self.is_valid_pdf(content):
                errors.append("El PDF parece estar corrupto")
        
        # 5. Virus scan (ClamAV o similar)
        if not await self.virus_scan(content):
            errors.append("El archivo no pasó el escaneo de seguridad")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            mime_type=mime,
            file_size=len(content),
        )
```

## 4. OCR (Optical Character Recognition)

### Estrategia dual: local + cloud

```python
class OCRProcessor:
    """
    Intenta primero con Tesseract (local, gratis).
    Si la calidad es baja, usa Google Cloud Vision (más preciso pero con costo).
    """
    
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        # 1. Preprocesamiento de imagen
        processed = self.preprocess(image_bytes)
        
        # 2. Tesseract (local)
        tesseract_result = await self.tesseract_ocr(processed)
        
        # 3. Evaluar calidad
        if tesseract_result.confidence >= 0.8:
            return tesseract_result
        
        # 4. Fallback a Cloud Vision si la calidad es baja
        cloud_result = await self.cloud_vision_ocr(image_bytes)
        return cloud_result
    
    def preprocess(self, image_bytes: bytes) -> bytes:
        """Mejora la imagen para OCR"""
        img = Image.open(BytesIO(image_bytes))
        
        # Convertir a escala de grises
        img = img.convert("L")
        
        # Binarización (Otsu)
        img_array = np.array(img)
        threshold = threshold_otsu(img_array)
        img_array = (img_array > threshold).astype(np.uint8) * 255
        
        # Deskew (corregir rotación)
        img_array = self.deskew(img_array)
        
        # Denoise
        img_array = cv2.fastNlMeansDenoising(img_array)
        
        return img_array
    
    async def tesseract_ocr(self, image: np.ndarray) -> OCRResult:
        """OCR local con Tesseract"""
        text = pytesseract.image_to_string(
            image, 
            lang="spa+eng",  # Español + Inglés
            config="--oem 3 --psm 6"  # LSTM engine, uniform block
        )
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        confidence = np.mean([int(c) for c in data["conf"] if int(c) > 0]) / 100
        
        return OCRResult(text=text, confidence=confidence, method="tesseract")
    
    async def cloud_vision_ocr(self, image_bytes: bytes) -> OCRResult:
        """OCR en la nube con Google Cloud Vision"""
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.document_text_detection(image=image)
        
        text = response.full_text_annotation.text
        confidence = np.mean([
            p.confidence 
            for page in response.full_text_annotation.pages
            for block in page.blocks
            for p in block.paragraphs
        ])
        
        return OCRResult(text=text, confidence=confidence, method="cloud_vision")
```

## 5. Clasificación de documentos

```python
class DocumentClassifier:
    """Clasifica el documento por tipo usando el LLM"""
    
    async def classify(self, text: str, filename: str) -> DocumentClassification:
        prompt = f"""
        Analiza el siguiente texto extraído de un documento médico y clasifícalo.
        
        Nombre del archivo: {filename}
        Texto extraído (primeros 2000 chars): {text[:2000]}
        
        Clasifica en una de estas categorías:
        - lab_result: Resultado de laboratorio (hemograma, química, etc.)
        - prescription: Receta médica
        - medical_report: Informe médico (alta, consulta, etc.)
        - imaging_report: Informe de estudio de imagen
        - clinical_image: Imagen clínica (foto de lesión, etc.)
        - other: Otro documento médico
        
        Retorna:
        - category: la categoría
        - confidence: confianza (0-1)
        - subcategory: subcategoría si aplica (ej: "hemograma", "perfil lipídico")
        - detected_entities: lista de entidades médicas detectadas
        """
        
        result = await llm.generate(prompt, response_format=DocumentClassification)
        return result
```

## 6. Extracción de datos clínicos

### Para resultados de laboratorio

```python
class LabResultExtractor:
    """Extrae valores de laboratorio estructurados del texto OCR"""
    
    async def extract(self, text: str) -> LabExtractionResult:
        prompt = f"""
        Del siguiente texto de un resultado de laboratorio, extrae TODOS los valores.
        
        Texto:
        {text}
        
        Para cada valor extraído, reporta:
        - analyte: nombre del analito (normalizado)
        - value: valor numérico
        - unit: unidad de medida
        - reference_range: rango de referencia (si está en el documento)
        - flag: "normal", "high", "low", "critical" (si puedes determinar)
        
        Retorna como JSON array.
        """
        
        values = await llm.generate(prompt, response_format=list[LabValue])
        
        # Validar contra nuestros rangos de referencia
        for v in values:
            v.flag = self.check_against_reference(v)
        
        return LabExtractionResult(values=values, raw_text=text)
    
    def check_against_reference(self, value: LabValue) -> str:
        """Compara el valor contra nuestros rangos de referencia curados"""
        ref = self.reference_db.get(value.analyte)
        if not ref:
            return "unknown"
        
        if value.value < ref.critical_low:
            return "critical_low"
        elif value.value < ref.range_min:
            return "low"
        elif value.value > ref.critical_high:
            return "critical_high"
        elif value.value > ref.range_max:
            return "high"
        return "normal"
```

### Para recetas médicas

```python
class PrescriptionExtractor:
    """Extrae medicamentos, dosis y frecuencia de una receta"""
    
    async def extract(self, text: str) -> PrescriptionExtractionResult:
        prompt = f"""
        Del siguiente texto de una receta médica, extrae TODOS los medicamentos prescritos.
        
        Texto:
        {text}
        
        Para cada medicamento:
        - name: nombre del medicamento (genérico si es posible)
        - dosage: dosis
        - frequency: frecuencia
        - route: vía de administración
        - duration: duración del tratamiento (si se indica)
        - notes: notas adicionales
        """
        
        medications = await llm.generate(prompt, response_format=list[PrescriptionItem])
        
        # Normalizar nombres con RxNorm si está disponible
        for med in medications:
            med.normalized_name = await self.normalize_drug_name(med.name)
        
        return PrescriptionExtractionResult(medications=medications)
```

## 7. Almacenamiento

### Base de datos

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id),
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Metadata del archivo
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,  -- nombre en S3
    mime_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,
    storage_path TEXT NOT NULL,     -- path en S3
    
    -- Clasificación
    document_type VARCHAR(50) NOT NULL,  -- lab_result, prescription, etc.
    document_subtype VARCHAR(100),        -- hemograma, perfil_lipidico, etc.
    
    -- Texto extraído
    extracted_text TEXT,
    ocr_confidence FLOAT,
    ocr_method VARCHAR(50),
    
    -- Datos estructurados extraídos
    extracted_data JSONB,          -- valores de lab, medicamentos, etc.
    
    -- Vector
    embedding vector(1536),
    
    -- Control
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    processing_status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, done, failed
    
    CONSTRAINT valid_status CHECK (processing_status IN ('pending', 'processing', 'done', 'failed'))
);

CREATE INDEX idx_docs_case ON documents(case_id);
CREATE INDEX idx_docs_type ON documents(document_type);
CREATE INDEX idx_docs_status ON documents(processing_status);
```

### S3/MinIO

```python
class DocumentStorage:
    """Almacena archivos en S3/MinIO"""
    
    async def store(self, file: UploadFile, case_id: str) -> StorageResult:
        # Generar nombre único
        ext = Path(file.filename).suffix
        stored_name = f"{case_id}/{uuid4()}{ext}"
        
        # Subir a S3
        content = await file.read()
        await self.s3.put_object(
            Bucket=self.bucket,
            Key=stored_name,
            Body=content,
            ContentType=file.content_type,
            ServerSideEncryption="AES256",  # Encriptación at rest
        )
        
        return StorageResult(
            stored_filename=stored_name,
            storage_path=f"s3://{self.bucket}/{stored_name}",
            file_size=len(content),
        )
```

## 8. Flujo completo de upload (API)

```python
@router.post("/api/v1/documents/upload")
async def upload_document(
    file: UploadFile,
    case_id: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    # 1. Validar
    validation = await validator.validate(file)
    if not validation.valid:
        raise HTTPException(400, detail=validation.errors)
    
    # 2. Almacenar en S3
    storage = await doc_storage.store(file, case_id)
    
    # 3. Crear registro en DB
    doc_record = await db.create_document(
        case_id=case_id,
        user_id=current_user.id,
        original_filename=file.filename,
        stored_filename=storage.stored_filename,
        storage_path=storage.storage_path,
        mime_type=validation.mime_type,
        file_size=storage.file_size,
    )
    
    # 4. Procesar en background (no bloquear al usuario)
    background_tasks.add_task(process_document, doc_record.id)
    
    return {"document_id": doc_record.id, "status": "processing"}


async def process_document(document_id: str):
    """Proceso en background para procesar el documento"""
    doc = await db.get_document(document_id)
    
    try:
        await db.update_document_status(document_id, "processing")
        
        # 1. Obtener bytes del archivo
        file_bytes = await doc_storage.download(doc.storage_path)
        
        # 2. Extraer texto (OCR si es necesario)
        if doc.mime_type.startswith("image/") or is_scanned_pdf(file_bytes):
            ocr_result = await ocr.extract_text(file_bytes)
            text = ocr_result.text
            confidence = ocr_result.confidence
            method = ocr_result.method
        elif doc.mime_type == "application/pdf":
            text = extract_pdf_text(file_bytes)
            confidence = 1.0
            method = "direct"
        elif "wordprocessing" in doc.mime_type:
            text = extract_docx_text(file_bytes)
            confidence = 1.0
            method = "direct"
        
        # 3. Clasificar
        classification = await classifier.classify(text, doc.original_filename)
        
        # 4. Extraer datos estructurados según tipo
        extracted_data = None
        if classification.category == "lab_result":
            extracted_data = await lab_extractor.extract(text)
        elif classification.category == "prescription":
            extracted_data = await prescription_extractor.extract(text)
        
        # 5. Generar embedding
        embedding = await embedder.embed(text)
        
        # 6. Actualizar registro
        await db.update_document(document_id, {
            "extracted_text": text,
            "ocr_confidence": confidence,
            "ocr_method": method,
            "document_type": classification.category,
            "document_subtype": classification.subcategory,
            "extracted_data": extracted_data.dict() if extracted_data else None,
            "embedding": embedding,
            "processing_status": "done",
            "processed_at": datetime.utcnow(),
        })
        
        # 7. Crear hechos clínicos a partir de los datos extraídos
        if extracted_data:
            await create_clinical_facts_from_document(doc.case_id, extracted_data)
        
    except Exception as e:
        await db.update_document_status(document_id, "failed")
        logger.error(f"Error processing document {document_id}: {e}")
```
