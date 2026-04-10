# 05 — Base de Conocimiento Médico y Estrategia RAG

## 1. El problema

Los LLMs tienen conocimiento médico general pero no actualizado, no verificado, y propenso a alucinaciones. Para un sistema clínico serio, necesitamos **grounding**: que cada respuesta se base en fuentes médicas verificables.

## 2. Estrategia general

```
┌─────────────────────────────────────────┐
│          FUENTES DE CONOCIMIENTO         │
│                                          │
│  Abiertas    Licenciadas    Propias      │
│  (scraping)  (APIs/docs)    (curadas)    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│         PIPELINE DE INGESTA              │
│  Scraping → Limpieza → Chunking →        │
│  Embedding → Indexación                   │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│         VECTOR STORE (pgvector)          │
│  Embeddings indexados por:               │
│  - Especialidad                          │
│  - Tipo (guía, fármaco, condición)       │
│  - Fuente                                │
│  - Nivel de evidencia                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│          RAG RETRIEVAL                   │
│  Query → Búsqueda semántica →            │
│  Re-ranking → Contexto a agentes         │
└─────────────────────────────────────────┘
```

## 3. Fuentes de datos médicos

### 3.1 Fuentes abiertas (scrapeables)

| Fuente | URL | Qué contiene | Licencia | Prioridad |
|--------|-----|-------------|----------|-----------|
| **MedlinePlus** | medlineplus.gov | Información médica para pacientes, condiciones, medicamentos, procedimientos | Dominio público (NIH/NLM) | ALTA |
| **WHO ICD-11** | icd.who.int | Clasificación internacional de enfermedades | CC BY-ND 3.0 IGO | ALTA |
| **PubMed/MEDLINE** | pubmed.ncbi.nlm.nih.gov | Abstracts de artículos científicos médicos | Dominio público (abstracts) | MEDIA |
| **ClinicalTrials.gov** | clinicaltrials.gov | Ensayos clínicos activos y resultados | Dominio público | BAJA (MVP) |
| **FDA Drug Labels** | labels.fda.gov | Prospectos de medicamentos aprobados por FDA | Dominio público | MEDIA |
| **VADEMECUM** | vademecum.es | Medicamentos en español (Latam/España) | Uso educativo | ALTA |
| **MSD Manual** | msdmanuals.com | Manual médico completo para profesionales y pacientes | Acceso abierto online | ALTA |
| **Drugs.com** | drugs.com | Interacciones, efectos adversos, dosificación | Acceso abierto online | MEDIA |
| **Guías de práctica clínica** | Varios ministerios de salud | Guías clínicas nacionales por país | Públicas | ALTA |
| **OpenFDA** | open.fda.gov | API abierta de medicamentos, eventos adversos | Dominio público | MEDIA |
| **SNOMED CT** | snomed.org | Terminología clínica estandarizada | Licencia gratuita para uso | ALTA |
| **LOINC** | loinc.org | Códigos de laboratorio universales | Licencia gratuita | MEDIA |

### 3.2 Fuentes con API

| Fuente | API | Qué provee | Costo |
|--------|-----|-----------|-------|
| **OpenFDA** | api.fda.gov | Medicamentos, eventos adversos, recalls | Gratis |
| **PubMed E-utilities** | eutils.ncbi.nlm.nih.gov | Búsqueda de artículos científicos | Gratis (con API key) |
| **UMLS** | uts-ws.nlm.nih.gov | Terminología médica unificada | Gratis (requiere licencia) |
| **RxNorm** | rxnav.nlm.nih.gov | Normalización de nombres de medicamentos | Gratis |
| **ICD API** | icd.who.int/icdapi | Clasificación de enfermedades | Gratis |
| **DisGeNET** | disgenet.org | Asociaciones gen-enfermedad | Freemium |

### 3.3 Fuentes propias (curadas manualmente)

| Tipo | Contenido | Formato |
|------|----------|---------|
| Red Flags | Lista curada de señales de alarma por especialidad | YAML/JSON |
| Templates de anamnesis | Preguntas por área clínica | YAML |
| Mapas de derivación | Síntoma → Especialidad(es) | JSON |
| Valores de referencia lab | Rangos normales por analito, edad, sexo | JSON |
| Disclaimers | Textos legales por tipo de respuesta | Templates |

## 4. Pipeline de scraping

### 4.1 Arquitectura del scraper

```python
# scraper/base.py
class MedicalScraper(ABC):
    """Base class para todos los scrapers médicos"""
    
    source_name: str
    base_url: str
    rate_limit: float  # requests per second
    
    @abstractmethod
    async def scrape(self) -> list[MedicalDocument]:
        ...
    
    @abstractmethod
    async def get_update_delta(self, last_scrape: datetime) -> list[MedicalDocument]:
        """Solo obtiene documentos nuevos o actualizados"""
        ...

class MedicalDocument:
    source: str                    # Nombre de la fuente
    source_url: str                # URL original
    title: str                     # Título del documento
    content: str                   # Texto completo
    category: str                  # "condition", "medication", "procedure", "guideline"
    specialty: list[str]           # Especialidades relacionadas
    language: str                  # "es", "en"
    evidence_level: Optional[str]  # Nivel de evidencia si aplica
    last_updated: datetime         # Cuándo se actualizó en la fuente
    scraped_at: datetime           # Cuándo lo scrapeamos
    metadata: dict                 # Datos adicionales específicos de la fuente
```

### 4.2 Scraper de MedlinePlus (ejemplo completo)

```python
# scraper/medlineplus.py
class MedlinePlusScraper(MedicalScraper):
    """
    MedlinePlus tiene contenido en español, es de dominio público (NIH),
    y está bien estructurado. Es nuestra fuente principal.
    """
    source_name = "medlineplus"
    base_url = "https://medlineplus.gov"
    rate_limit = 1.0  # 1 req/sec (respetar ToS)
    
    async def scrape_conditions(self) -> list[MedicalDocument]:
        """Scrapea todas las condiciones/enfermedades"""
        # MedlinePlus tiene un XML sitemap con todas las páginas
        sitemap_url = f"{self.base_url}/spanish/xml/topic_sitemap.xml"
        
        sitemap = await self.fetch_xml(sitemap_url)
        condition_urls = self.extract_condition_urls(sitemap)
        
        documents = []
        for url in condition_urls:
            await asyncio.sleep(1 / self.rate_limit)
            doc = await self.scrape_condition_page(url)
            if doc:
                documents.append(doc)
        
        return documents
    
    async def scrape_condition_page(self, url: str) -> MedicalDocument:
        """Scrapea una página individual de condición"""
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "html.parser")
        
        title = soup.select_one("h1.with-also").text.strip()
        
        # MedlinePlus tiene secciones bien definidas
        sections = {}
        for section in soup.select("div.section-body"):
            heading = section.find_previous("h2")
            if heading:
                sections[heading.text.strip()] = section.get_text(strip=True)
        
        content = "\n\n".join([
            f"## {k}\n{v}" for k, v in sections.items()
        ])
        
        return MedicalDocument(
            source="medlineplus",
            source_url=url,
            title=title,
            content=content,
            category="condition",
            specialty=self.infer_specialties(title, content),
            language="es",
            last_updated=self.extract_date(soup),
            scraped_at=datetime.utcnow(),
        )
    
    async def scrape_medications(self) -> list[MedicalDocument]:
        """Scrapea información de medicamentos"""
        # Similar a conditions pero desde la sección de medicamentos
        ...
    
    async def scrape_lab_tests(self) -> list[MedicalDocument]:
        """Scrapea información de pruebas de laboratorio"""
        ...
```

### 4.3 Scraper de VADEMECUM (medicamentos en español)

```python
# scraper/vademecum.py
class VademecumScraper(MedicalScraper):
    """
    VADEMECUM tiene información detallada de medicamentos en español.
    Incluye: indicaciones, contraindicaciones, interacciones, dosis.
    """
    source_name = "vademecum"
    base_url = "https://www.vademecum.es"
    rate_limit = 0.5  # Más conservador
    
    async def scrape_drug(self, drug_url: str) -> MedicalDocument:
        html = await self.fetch(drug_url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Extraer secciones: indicaciones, posología, contraindicaciones, 
        # interacciones, efectos adversos, embarazo/lactancia
        ...
```

### 4.4 Scraper de Guías Clínicas

```python
# scraper/clinical_guidelines.py
class ClinicalGuidelinesScraper(MedicalScraper):
    """
    Scrapea guías de práctica clínica de:
    - Ministerio de Salud (por país)
    - Sociedades médicas
    - Organizaciones internacionales (WHO, PAHO)
    """
    
    sources = [
        {
            "name": "MINSA Perú",
            "url": "https://www.gob.pe/minsa",
            "type": "government"
        },
        {
            "name": "Ministerio Salud Argentina",
            "url": "https://www.argentina.gob.ar/salud",
            "type": "government"
        },
        {
            "name": "OPS/PAHO",
            "url": "https://www.paho.org/es",
            "type": "international"
        },
    ]
```

### 4.5 Scheduler de scraping

```python
# scraper/scheduler.py
SCRAPING_SCHEDULE = {
    "medlineplus": {
        "frequency": "weekly",     # Scrapear cada semana
        "full_scrape": "monthly",  # Scrape completo cada mes
        "delta_scrape": "weekly",  # Solo cambios cada semana
    },
    "vademecum": {
        "frequency": "monthly",
        "full_scrape": "quarterly",
        "delta_scrape": "monthly",
    },
    "clinical_guidelines": {
        "frequency": "monthly",
        "full_scrape": "quarterly",
        "delta_scrape": "monthly",
    },
    "openfda": {
        "frequency": "weekly",     # API, no scraping
        "method": "api_fetch",
    },
}
```

## 5. Pipeline de procesamiento

### 5.1 Chunking

Los documentos médicos deben dividirse en chunks de tamaño apropiado para RAG:

```python
class MedicalChunker:
    """
    Chunking especializado para documentos médicos.
    Respeta secciones clínicas (no corta en medio de una sección).
    """
    
    def chunk(self, document: MedicalDocument) -> list[Chunk]:
        # 1. Intentar dividir por secciones (##, ###)
        sections = self.split_by_sections(document.content)
        
        chunks = []
        for section in sections:
            if self.count_tokens(section.text) <= MAX_CHUNK_TOKENS:
                # La sección cabe en un chunk
                chunks.append(Chunk(
                    text=section.text,
                    section_title=section.title,
                    source=document.source,
                    source_url=document.source_url,
                    document_title=document.title,
                    specialty=document.specialty,
                    category=document.category,
                ))
            else:
                # La sección es muy larga, dividir por párrafos
                sub_chunks = self.split_by_paragraphs(section, MAX_CHUNK_TOKENS)
                chunks.extend(sub_chunks)
        
        return chunks

# Configuración
MAX_CHUNK_TOKENS = 512      # Tamaño máximo de chunk
CHUNK_OVERLAP = 50          # Tokens de overlap entre chunks
```

### 5.2 Embedding

```python
class MedicalEmbedder:
    """Genera embeddings para chunks médicos"""
    
    def __init__(self):
        # Usamos text-embedding-3-small de OpenAI (1536 dims)
        # Alternativa: un modelo médico especializado como BioMedBERT
        self.model = "text-embedding-3-small"
    
    async def embed_chunks(self, chunks: list[Chunk]) -> list[ChunkWithEmbedding]:
        # Batch embedding para eficiencia
        texts = [c.text for c in chunks]
        embeddings = await openai.embeddings.create(
            model=self.model,
            input=texts,
        )
        
        return [
            ChunkWithEmbedding(
                **chunk.dict(),
                embedding=emb.embedding
            )
            for chunk, emb in zip(chunks, embeddings.data)
        ]
```

### 5.3 Indexación en pgvector

```sql
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Metadata del documento
    source VARCHAR(100) NOT NULL,
    source_url TEXT,
    document_title TEXT NOT NULL,
    section_title TEXT,
    
    -- Contenido
    content TEXT NOT NULL,
    
    -- Clasificación
    category VARCHAR(50) NOT NULL,   -- condition, medication, guideline, lab_test
    specialty TEXT[] NOT NULL,         -- array de especialidades
    language VARCHAR(10) DEFAULT 'es',
    evidence_level VARCHAR(20),       -- high, moderate, low, expert_opinion
    
    -- Vector
    embedding vector(1536) NOT NULL,
    
    -- Control
    scraped_at TIMESTAMPTZ NOT NULL,
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,
    
    -- Índices
    CONSTRAINT valid_category CHECK (category IN ('condition', 'medication', 'guideline', 'lab_test', 'procedure', 'symptom', 'general'))
);

-- Índice vectorial para búsqueda semántica
CREATE INDEX idx_knowledge_embedding 
    ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 200);

-- Índices para filtrado
CREATE INDEX idx_knowledge_category ON knowledge_chunks(category);
CREATE INDEX idx_knowledge_specialty ON knowledge_chunks USING GIN(specialty);
CREATE INDEX idx_knowledge_source ON knowledge_chunks(source);
CREATE INDEX idx_knowledge_active ON knowledge_chunks(is_active) WHERE is_active = true;
```

## 6. RAG Retrieval

### 6.1 Búsqueda de conocimiento

```python
class KnowledgeRetriever:
    """
    Retriever médico con búsqueda semántica y filtros.
    """
    
    async def search(
        self,
        query: str,
        specialties: list[str] = None,
        categories: list[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.7,
    ) -> list[RetrievalResult]:
        
        query_embedding = await self.embed(query)
        
        sql = """
            SELECT 
                id, content, document_title, section_title,
                source, source_url, category, specialty,
                evidence_level,
                1 - (embedding <=> $1) AS similarity
            FROM knowledge_chunks
            WHERE is_active = true
              AND 1 - (embedding <=> $1) >= $5
              AND ($2::text[] IS NULL OR specialty && $2)
              AND ($3::text[] IS NULL OR category = ANY($3))
            ORDER BY similarity DESC
            LIMIT $4
        """
        
        results = await self.db.fetch(
            sql, query_embedding, specialties, categories, top_k, min_similarity
        )
        
        return [RetrievalResult(**r) for r in results]
    
    async def search_with_reranking(
        self,
        query: str,
        **kwargs
    ) -> list[RetrievalResult]:
        """Búsqueda con re-ranking para mayor precisión"""
        
        # 1. Búsqueda amplia (top 20)
        candidates = await self.search(query, top_k=20, **kwargs)
        
        # 2. Re-ranking con LLM
        reranked = await self.rerank(query, candidates, top_k=5)
        
        return reranked
    
    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 5
    ) -> list[RetrievalResult]:
        """Usa el LLM para re-rankear por relevancia clínica"""
        
        prompt = f"""
        Consulta clínica: {query}
        
        Documentos candidatos:
        {self.format_candidates(candidates)}
        
        Ordena los documentos por relevancia clínica para la consulta.
        Retorna los IDs en orden de relevancia (más relevante primero).
        Máximo {top_k} resultados.
        """
        # ... LLM call + reordering
```

### 6.2 Inyección de conocimiento en agentes

```python
async def prepare_agent_context(
    case_state: ClinicalCaseState,
    agent_specialty: str
) -> str:
    """
    Prepara el contexto de conocimiento para un agente específico.
    Combina: hechos del caso + conocimiento relevante + memoria clínica
    """
    
    # 1. Conocimiento relevante al motivo de consulta
    knowledge = await retriever.search_with_reranking(
        query=case_state["chief_complaint"],
        specialties=[agent_specialty],
        top_k=5
    )
    
    # 2. Si hay síntomas específicos, buscar por cada uno
    symptom_knowledge = []
    for symptom in case_state["symptoms"]:
        results = await retriever.search(
            query=symptom.description,
            categories=["condition", "symptom"],
            top_k=2
        )
        symptom_knowledge.extend(results)
    
    # 3. Si hay medicamentos mencionados, buscar interacciones
    if case_state.get("medications"):
        drug_knowledge = await retriever.search(
            query=" ".join([m.name for m in case_state["medications"]]),
            categories=["medication"],
            top_k=3
        )
    
    # 4. Formatear contexto
    context = "## Evidencia médica relevante\n\n"
    for k in knowledge:
        context += f"### {k.document_title} ({k.source})\n{k.content}\n\n"
    
    return context
```

## 7. Datos propios curados

### 7.1 Red Flags (señales de alarma)

```yaml
# data/red_flags.yaml
cardiovascular:
  high_urgency:
    - pattern: "dolor torácico + disnea"
      action: "escalation_immediate"
      message: "Estos síntomas requieren evaluación médica URGENTE"
    - pattern: "dolor torácico + irradiación brazo/mandíbula"
      action: "escalation_immediate"
    - pattern: "síncope + dolor torácico"
      action: "escalation_immediate"
  medium_urgency:
    - pattern: "palpitaciones + mareo"
      action: "recommend_24h"
    - pattern: "edema miembros inferiores + disnea"
      action: "recommend_24h"

neurological:
  high_urgency:
    - pattern: "debilidad unilateral súbita"
      action: "escalation_immediate"
      message: "Posible ACV. Busque atención de EMERGENCIA inmediatamente."
    - pattern: "pérdida súbita de visión o habla"
      action: "escalation_immediate"
    - pattern: "cefalea severa súbita ('la peor')"
      action: "escalation_immediate"

# ... más por especialidad
```

### 7.2 Valores de referencia de laboratorio

```yaml
# data/lab_references.yaml
hemograma:
  hemoglobina:
    unit: "g/dL"
    ranges:
      adult_male: { min: 13.5, max: 17.5 }
      adult_female: { min: 12.0, max: 16.0 }
      child_1_6: { min: 9.5, max: 14.0 }
      newborn: { min: 14.0, max: 24.0 }
    critical_low: 7.0
    critical_high: 20.0
    interpretation:
      low: "Posible anemia. Evaluar según contexto clínico."
      high: "Evaluar policitemia o deshidratación."
      critical_low: "URGENTE: Anemia severa. Requiere evaluación inmediata."
  
  leucocitos:
    unit: "x10³/μL"
    ranges:
      adult: { min: 4.5, max: 11.0 }
      child: { min: 5.0, max: 15.0 }
    critical_low: 2.0
    critical_high: 30.0
    
  plaquetas:
    unit: "x10³/μL"
    ranges:
      adult: { min: 150, max: 400 }
    critical_low: 50
    critical_high: 1000

quimica_sanguinea:
  glucosa:
    unit: "mg/dL"
    ranges:
      fasting: { min: 70, max: 100 }
      random: { min: 70, max: 140 }
    critical_low: 40
    critical_high: 400
    interpretation:
      elevated_fasting: "Glucosa en ayunas elevada. Considerar prediabetes/diabetes."
      critical_low: "URGENTE: Hipoglucemia severa."
      critical_high: "URGENTE: Hiperglucemia severa."

# ... hemoglobina glicosilada, perfil lipídico, función renal, hepática, etc.
```

### 7.3 Mapas síntoma → especialidad

```yaml
# data/symptom_specialty_map.yaml
dolor_toracico:
  primary: [cardiologia, neumologia]
  secondary: [gastroenterologia, traumatologia]
  red_flag_check: true
  
dolor_abdominal:
  primary: [gastroenterologia, cirugia_general]
  secondary: [ginecologia, urologia, medicina_interna]
  context_modifiers:
    - if: "embarazo"
      add: [obstetricia]
      priority: "high"
    - if: "fiebre + rebote"
      add: [cirugia_general]
      priority: "urgent"

cefalea:
  primary: [neurologia, medicina_general]
  secondary: [oftalmologia, otorrinolaringologia]
  context_modifiers:
    - if: "súbita + severa"
      red_flag: true
      action: "escalation"
    - if: "visual + náuseas"
      add: [oftalmologia]

# ... más mapas
```

## 8. Actualización y mantenimiento

### Estrategia de actualización

```yaml
update_strategy:
  scraped_sources:
    frequency: "semanal (delta) + mensual (full)"
    validation: "automática + revisión manual trimestral"
    versioning: "cada scrape genera nueva versión, anterior se marca inactive"
    
  api_sources:
    frequency: "diaria para FDA alerts, semanal para resto"
    method: "API fetch directo"
    
  curated_data:
    frequency: "manual, según necesidad"
    review: "médico revisor cada 3 meses"
    versioning: "git (archivos YAML/JSON)"
    
  embeddings:
    regeneration: "cuando se actualiza el modelo de embedding"
    incremental: "solo re-embed chunks modificados"
```

## 9. Métricas de la knowledge base

```yaml
kpi:
  coverage:
    - "% de condiciones del ICD-10 cubiertas"
    - "% de medicamentos del vademécum local cubiertos"
    - "# de guías clínicas indexadas"
    
  quality:
    - "Precisión de retrieval (relevance score promedio)"
    - "% de respuestas con al menos 1 fuente citada"
    - "% de alucinaciones detectadas en validación"
    
  freshness:
    - "Edad promedio de los chunks (días desde scrape)"
    - "% de chunks actualizados en último mes"
    - "# de fuentes con scraping fallido"
```
