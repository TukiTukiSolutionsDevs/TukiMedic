# 14 — Fuentes de Datos Médicos y Estrategia de Scraping

## 1. Visión general

La base de conocimiento médico de MedAgent se construye a partir de **4 tipos de fuentes**:

```
┌───────────────────────────────────────────────────────┐
│                FUENTES DE CONOCIMIENTO                 │
├──────────────┬──────────────┬────────────┬────────────┤
│   SCRAPING   │    APIs      │  CURADAS   │  ESTÁNDAR  │
│   (web)      │  (abiertas)  │ (manuales) │ (códigos)  │
├──────────────┼──────────────┼────────────┼────────────┤
│ MedlinePlus  │ OpenFDA      │ Red flags  │ ICD-10/11  │
│ VADEMECUM    │ PubMed API   │ Lab refs   │ SNOMED CT  │
│ MSD Manual   │ RxNorm       │ Templates  │ LOINC      │
│ Drugs.com    │ ICD API      │ Mapas S→E  │ ATC        │
│ Guías clín.  │ UMLS         │ Disclaimers│ CIE-10     │
│ OPS/PAHO     │ DisGeNET     │            │            │
└──────────────┴──────────────┴────────────┴────────────┘
```

## 2. Fuentes por scraping web — Detalle completo

### 2.1 MedlinePlus (PRIORIDAD MÁXIMA)

| Campo | Detalle |
|-------|---------|
| **URL** | https://medlineplus.gov/spanish/ |
| **Idioma** | Español (e inglés) |
| **Licencia** | Dominio público (NIH/NLM) — libre uso |
| **Contenido** | ~1000 condiciones, ~1000 medicamentos, ~200 pruebas de lab |
| **Estructura** | HTML bien estructurado con secciones predecibles |
| **Rate limit** | Respetar robots.txt, ~1 req/sec |
| **Actualización** | Las páginas se actualizan regularmente por NIH |

**Qué scrapear:**

```python
MEDLINEPLUS_TARGETS = {
    "conditions": {
        "sitemap": "https://medlineplus.gov/spanish/xml/topic_sitemap.xml",
        "sections_to_extract": [
            "¿Qué es?",
            "Síntomas",
            "Causas",
            "Diagnóstico",
            "Tratamiento",
            "Prevención",
            "Cuándo contactar a un profesional médico",
        ],
        "output_category": "condition",
        "priority": "HIGH",
    },
    "medications": {
        "sitemap": "https://medlineplus.gov/spanish/xml/druginformation_sitemap.xml",
        "sections_to_extract": [
            "¿Para cuáles condiciones se prescribe?",
            "¿Cómo se debe usar?",
            "Efectos secundarios",
            "Precauciones especiales",
            "Interacciones",
            "Almacenamiento",
        ],
        "output_category": "medication",
        "priority": "HIGH",
    },
    "lab_tests": {
        "base_url": "https://medlineplus.gov/spanish/laboratorytests.html",
        "sections_to_extract": [
            "¿Qué es?",
            "¿Para qué se usa?",
            "¿Por qué necesito?",
            "¿Qué significan los resultados?",
        ],
        "output_category": "lab_test",
        "priority": "MEDIUM",
    },
}
```

**Ejemplo de scraping:**

```python
class MedlinePlusScraper:
    BASE_URL = "https://medlineplus.gov"
    RATE_LIMIT = 1.0  # 1 request por segundo
    
    async def scrape_all_conditions_es(self) -> list[MedicalDocument]:
        """Scrapea TODAS las condiciones en español"""
        
        # 1. Obtener sitemap XML
        sitemap_url = f"{self.BASE_URL}/spanish/xml/topic_sitemap.xml"
        xml = await self.fetch(sitemap_url)
        urls = self.parse_sitemap(xml)
        
        logger.info(f"Encontradas {len(urls)} condiciones para scrapear")
        
        documents = []
        for i, url in enumerate(urls):
            try:
                await asyncio.sleep(1 / self.RATE_LIMIT)
                doc = await self.scrape_page(url)
                if doc:
                    documents.append(doc)
                    logger.info(f"[{i+1}/{len(urls)}] {doc.title}")
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                continue
        
        return documents
    
    async def scrape_page(self, url: str) -> MedicalDocument:
        """Scrapea una página individual"""
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Título
        title_el = soup.select_one("h1.with-also, h1")
        title = title_el.text.strip() if title_el else "Sin título"
        
        # Secciones
        content_parts = []
        for section_div in soup.select("div.section-body"):
            heading = section_div.find_previous(["h2", "h3"])
            if heading:
                section_title = heading.text.strip()
                section_text = section_div.get_text(separator="\n", strip=True)
                content_parts.append(f"## {section_title}\n\n{section_text}")
        
        # También "also known as" y "related topics"
        also_known = soup.select_one(".defined-term")
        
        content = "\n\n".join(content_parts)
        
        return MedicalDocument(
            source="medlineplus",
            source_url=url,
            title=title,
            content=content,
            category="condition",
            specialty=self.infer_specialties(title, content),
            language="es",
            evidence_level="high",  # NIH es fuente de alta evidencia
            scraped_at=datetime.utcnow(),
            metadata={
                "also_known_as": also_known.text if also_known else None,
                "page_type": "condition",
            }
        )
```

### 2.2 VADEMECUM

| Campo | Detalle |
|-------|---------|
| **URL** | https://www.vademecum.es |
| **Idioma** | Español |
| **Contenido** | Medicamentos: indicaciones, dosis, contraindicaciones, interacciones |
| **Rate limit** | Conservador: 1 req/2sec |
| **Nota legal** | Uso educativo — verificar ToS |

**Qué scrapear:**

```python
VADEMECUM_TARGETS = {
    "drugs": {
        "index": "https://www.vademecum.es/principios-activos",
        "sections": [
            "Mecanismo de acción",
            "Indicaciones terapéuticas", 
            "Posología",
            "Contraindicaciones",
            "Advertencias y precauciones",
            "Interacciones",
            "Embarazo y lactancia",
            "Reacciones adversas",
        ],
        "output_category": "medication",
    }
}
```

### 2.3 MSD Manual (Manual Merck)

| Campo | Detalle |
|-------|---------|
| **URL** | https://www.msdmanuals.com/es |
| **Idioma** | Español |
| **Contenido** | Enciclopedia médica completa para profesionales y pacientes |
| **Versiones** | Profesional + Para el paciente |
| **Rate limit** | 1 req/2sec |

**Qué scrapear:**

```python
MSD_TARGETS = {
    "patient_version": {
        "base": "https://www.msdmanuals.com/es/hogar",
        "categories": [
            "trastornos-del-corazón-y-los-vasos-sanguíneos",
            "trastornos-gastrointestinales",
            "trastornos-del-pulmón-y-las-vías-respiratorias",
            "trastornos-del-cerebro-médula-espinal-y-nervios",
            "trastornos-de-la-salud-mental",
            "trastornos-hormonales-y-metabólicos",
            # ... todas las categorías
        ],
        "output_category": "condition",
        "audience": "patient",
    },
    "professional_version": {
        "base": "https://www.msdmanuals.com/es/professional",
        "output_category": "guideline",
        "audience": "professional",
        "priority": "MEDIUM",  # Post-MVP
    }
}
```

### 2.4 Guías de Práctica Clínica

| Fuente | País | URL |
|--------|------|-----|
| MINSA | Perú | gob.pe/minsa |
| MSal | Argentina | argentina.gob.ar/salud |
| Secretaría de Salud | México | gob.mx/salud |
| OPS/PAHO | Internacional | paho.org/es |
| WHO | Internacional | who.int/es |

```python
GUIDELINE_SOURCES = [
    {
        "name": "OPS - Guías de Atención Primaria",
        "url": "https://www.paho.org/es/documentos",
        "search_terms": ["guía clínica", "protocolo atención", "manejo"],
        "format": "PDF",
        "processing": "download_pdf → OCR/extract → chunk → embed"
    },
    {
        "name": "WHO Guidelines",
        "url": "https://www.who.int/publications/guidelines",
        "search_terms": ["clinical guideline", "treatment"],
        "format": "PDF",
        "language": "en",  # Traducir o usar en inglés
    }
]
```

### 2.5 Drugs.com (interacciones)

| Campo | Detalle |
|-------|---------|
| **URL** | https://www.drugs.com |
| **Idioma** | Inglés (traducir automáticamente o usar como complemento) |
| **Contenido** | Interacciones medicamentosas, efectos adversos detallados |
| **Prioridad** | MEDIA (complementa VADEMECUM) |

## 3. Fuentes por API

### 3.1 OpenFDA

```python
class OpenFDAClient:
    """
    API abierta de la FDA para medicamentos, eventos adversos, recalls.
    NO requiere API key. Rate limit: 240 req/min sin key, 120K/día con key.
    """
    BASE_URL = "https://api.fda.gov"
    
    async def search_drug(self, drug_name: str) -> dict:
        """Buscar información de un medicamento"""
        url = f"{self.BASE_URL}/drug/label.json"
        params = {
            "search": f'openfda.brand_name:"{drug_name}" OR openfda.generic_name:"{drug_name}"',
            "limit": 5
        }
        return await self.get(url, params)
    
    async def get_adverse_events(self, drug_name: str, limit: int = 10) -> dict:
        """Obtener eventos adversos reportados"""
        url = f"{self.BASE_URL}/drug/event.json"
        params = {
            "search": f'patient.drug.medicinalproduct:"{drug_name}"',
            "count": "patient.reaction.reactionmeddrapt.exact",
            "limit": limit
        }
        return await self.get(url, params)
    
    async def check_drug_interactions(self, drugs: list[str]) -> dict:
        """Verificar interacciones entre medicamentos"""
        # OpenFDA no tiene endpoint directo de interacciones
        # Se combina con RxNorm para esto
        ...
```

### 3.2 PubMed E-utilities

```python
class PubMedClient:
    """
    API de PubMed para buscar artículos científicos.
    Requiere API key para más de 3 req/sec.
    """
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def search_articles(
        self, 
        query: str, 
        max_results: int = 10
    ) -> list[PubMedArticle]:
        """Buscar artículos relevantes"""
        # 1. Buscar IDs
        search_url = f"{self.BASE_URL}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "sort": "relevance",
            "retmode": "json",
            "api_key": self.api_key,
        }
        search_result = await self.get(search_url, params)
        ids = search_result["esearchresult"]["idlist"]
        
        # 2. Obtener abstracts
        fetch_url = f"{self.BASE_URL}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "rettype": "abstract",
            "retmode": "xml",
            "api_key": self.api_key,
        }
        articles = await self.get(fetch_url, params)
        
        return self.parse_articles(articles)
```

### 3.3 RxNorm (normalización de medicamentos)

```python
class RxNormClient:
    """
    API de la NLM para normalizar nombres de medicamentos.
    Gratis, sin API key. Rate limit: 20 req/sec.
    """
    BASE_URL = "https://rxnav.nlm.nih.gov/REST"
    
    async def normalize_drug_name(self, name: str) -> Optional[str]:
        """Normaliza un nombre de medicamento al nombre genérico"""
        url = f"{self.BASE_URL}/approximateTerm.json"
        params = {"term": name, "maxEntries": 1}
        result = await self.get(url, params)
        
        if result.get("approximateGroup", {}).get("candidate"):
            rxcui = result["approximateGroup"]["candidate"][0]["rxcui"]
            return await self.get_generic_name(rxcui)
        return None
    
    async def get_interactions(self, rxcuis: list[str]) -> list[dict]:
        """Verificar interacciones entre medicamentos por RXCUI"""
        url = f"{self.BASE_URL}/interaction/list.json"
        params = {"rxcuis": "+".join(rxcuis)}
        return await self.get(url, params)
```

### 3.4 ICD API (clasificación de enfermedades)

```python
class ICDClient:
    """
    API de la WHO para ICD-10/ICD-11.
    Requiere registro gratuito para API token.
    """
    BASE_URL = "https://id.who.int/icd"
    
    async def search_condition(self, term: str) -> list[ICDCode]:
        """Buscar código ICD por término"""
        url = f"{self.BASE_URL}/release/11/2024-01/mms/search"
        params = {
            "q": term,
            "useFlexisearch": "true",
            "flatResults": "true",
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept-Language": "es",
            "API-Version": "v2",
        }
        result = await self.get(url, params, headers)
        return self.parse_results(result)
```

## 4. Datos curados manualmente

### 4.1 Estructura de archivos curados

```
data/
├── red_flags/
│   ├── cardiovascular.yaml
│   ├── neurological.yaml
│   ├── psychiatric.yaml
│   ├── pediatric.yaml
│   ├── obstetric.yaml
│   └── general.yaml
│
├── lab_references/
│   ├── hemograma.yaml
│   ├── quimica_sanguinea.yaml
│   ├── perfil_lipidico.yaml
│   ├── funcion_renal.yaml
│   ├── funcion_hepatica.yaml
│   ├── perfil_tiroideo.yaml
│   ├── coagulacion.yaml
│   ├── orina.yaml
│   └── marcadores_especiales.yaml
│
├── specialty_maps/
│   ├── symptom_to_specialty.yaml
│   ├── condition_to_specialty.yaml
│   └── drug_to_specialty.yaml
│
├── anamnesis_templates/
│   ├── general.yaml
│   ├── cardiovascular.yaml
│   ├── gastrointestinal.yaml
│   ├── respiratory.yaml
│   ├── neurological.yaml
│   ├── musculoskeletal.yaml
│   ├── dermatological.yaml
│   ├── psychiatric.yaml
│   ├── pediatric.yaml
│   ├── gynecological.yaml
│   └── urological.yaml
│
├── disclaimers/
│   ├── initial.md
│   ├── per_response.md
│   ├── escalation.md
│   └── legal.md
│
└── emergency_numbers/
    ├── argentina.yaml
    ├── mexico.yaml
    ├── colombia.yaml
    ├── peru.yaml
    ├── chile.yaml
    └── espana.yaml
```

### 4.2 Ejemplo: template de anamnesis gastrointestinal

```yaml
# data/anamnesis_templates/gastrointestinal.yaml
name: "Anamnesis Gastrointestinal"
specialty: "gastroenterologia"
triggers:
  - "dolor abdominal"
  - "náuseas"
  - "vómitos"
  - "diarrea"
  - "estreñimiento"
  - "acidez"
  - "reflujo"
  - "sangre en heces"

questions:
  critical:
    - text: "¿Has notado sangre en las heces o heces negras?"
      type: "yes_no"
      red_flag: true
      if_yes: "Esto es un signo de alarma. ¿Es sangre roja brillante o las heces son oscuras/negras?"
      
    - text: "¿Has tenido fiebre junto con el dolor abdominal?"
      type: "yes_no"
      red_flag_combination: "dolor_abdominal + fiebre"
      
    - text: "¿El dolor es tan fuerte que no puedes moverte?"
      type: "yes_no"
      red_flag: true
      
  important:
    - text: "¿Dónde exactamente sientes el dolor?"
      type: "open"
      options: 
        - "Parte alta del abdomen (boca del estómago)"
        - "Alrededor del ombligo"
        - "Parte baja del abdomen"
        - "Lado derecho"
        - "Lado izquierdo"
        - "Todo el abdomen"
      
    - text: "¿Hace cuánto tiempo tienes estos síntomas?"
      type: "open"
      
    - text: "Del 1 al 10, ¿qué tan intenso es el dolor?"
      type: "scale_1_10"
      
    - text: "¿El dolor se relaciona con las comidas? ¿Mejora o empeora al comer?"
      type: "open"
      
    - text: "¿Hay algo que alivie el dolor? ¿Y algo que lo empeore?"
      type: "open"

  helpful:
    - text: "¿Has viajado recientemente?"
      type: "yes_no"
      relevance: "infeccion_parasitaria"
      
    - text: "¿Alguien en tu entorno tiene síntomas similares?"
      type: "yes_no"
      relevance: "infeccion_alimentaria"
      
    - text: "¿Has cambiado tu alimentación recientemente?"
      type: "yes_no"
      
    - text: "¿Tomas algún antiinflamatorio como ibuprofeno?"
      type: "yes_no"
      relevance: "gastritis_medicamentosa"
```

### 4.3 Ejemplo: números de emergencia

```yaml
# data/emergency_numbers/argentina.yaml
country: "Argentina"
code: "AR"
language: "es"

emergency:
  general: "107"
  police: "101"
  fire: "100"
  
mental_health:
  - name: "Centro de Asistencia al Suicida"
    number: "(011) 5275-1135"
    hours: "24/7"
  - name: "Línea de Salud Mental"
    number: "0800-999-0091"
    hours: "24/7"

poison_control:
  - name: "Hospital de Niños Ricardo Gutiérrez"
    number: "(011) 4962-6666"
    
gender_violence:
  - name: "Línea 144"
    number: "144"
    hours: "24/7"
```

## 5. Pipeline de ingesta completo

```
                    ┌─────────────────┐
                    │   SCHEDULER     │
                    │ (cron/celery)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Scraper  │  │ API      │  │ Manual   │
        │ Manager  │  │ Fetcher  │  │ Loader   │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │              │              │
             ▼              ▼              ▼
        ┌──────────────────────────────────────┐
        │         RAW DOCUMENT STORE            │
        │    (staging area antes de procesar)   │
        └───────────────────┬──────────────────┘
                            │
                    ┌───────▼───────┐
                    │  CLEANER      │
                    │  - HTML strip  │
                    │  - Normalize   │
                    │  - Deduplicate │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │  CHUNKER      │
                    │  - By section  │
                    │  - Max 512 tok │
                    │  - Overlap 50  │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │  EMBEDDER     │
                    │  - Batch embed │
                    │  - 1536 dims   │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │  INDEXER      │
                    │  - pgvector    │
                    │  - Metadata    │
                    │  - Specialty   │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │  VALIDATOR    │
                    │  - Spot check  │
                    │  - Quality     │
                    │  - Coverage    │
                    └───────────────┘
```

## 6. Métricas de la base de conocimiento

### KPIs a trackear

```yaml
coverage:
  total_chunks: "Número total de chunks indexados"
  by_source: "Chunks por fuente (MedlinePlus, VADEMECUM, etc.)"
  by_category: "Chunks por categoría (condition, medication, etc.)"
  by_specialty: "Chunks por especialidad"
  icd10_coverage: "% de códigos ICD-10 con al menos 1 chunk"
  
quality:
  avg_chunk_length: "Longitud promedio de chunk (tokens)"
  retrieval_precision: "Precisión de búsqueda (evaluación manual periódica)"
  citation_rate: "% de respuestas con al menos 1 fuente citada"
  
freshness:
  avg_age_days: "Edad promedio de chunks (días desde scrape)"
  stale_chunks: "Chunks no actualizados en >90 días"
  last_scrape_by_source: "Fecha del último scrape exitoso por fuente"
  failed_scrapes: "Scrapes fallidos en últimos 7 días"
```

## 7. Roadmap de ingesta por fase

| Fase | Fuentes | Chunks estimados |
|------|---------|-----------------|
| **MVP (Fase 1)** | Red flags (manual), Lab refs (manual), Templates (manual) | ~200 |
| **Fase 2** | MedlinePlus condiciones ES | ~5,000 |
| **Fase 3** | MedlinePlus medicamentos + VADEMECUM | ~10,000 |
| **Fase 4** | MSD Manual + Guías clínicas + PubMed abstracts | ~25,000 |
| **Fase 5** | OpenFDA + RxNorm + APIs complementarias | ~40,000 |
