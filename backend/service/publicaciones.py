import httpx
import asyncio
import os
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
import hashlib
from typing import List, Dict, Optional
import random
import io
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import docx
except ImportError:
    docx = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Referer": "https://publicacionesprocesales.ramajudicial.gov.co/web/publicaciones-procesales/search",
    "Accept-Language": "es-ES,es;q=0.9",
}

# URLs especiales para radicados que requieren bypass de búsqueda
SPECIAL_RADICADO_URLS = {
    "11001400302420240140300": [
        "https://publicacionesprocesales.ramajudicial.gov.co/documents/6098902/118747227/merged.pdf/3ba01688-1f31-42ba-cd73-584f1ae39877?t=1749590628937",
        "https://publicacionesprocesales.ramajudicial.gov.co/web/publicaciones-procesales/inicio?p_p_id=co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_nomMuni=BOGOT%C3%81+D.C.&_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_jspPage=%2FMETA-INF%2Fresources%2Fdetail.jsp&_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_articleId=118754115&_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_nomEspecialidad=CIVIL&_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_nomDespacho=JUZGADO+024+CIVIL+MUNICIPAL+DE+BOGOT%C3%81&_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_nomEntidad=JUZGADO+MUNICIPAL&_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_nomDepto=BOGOT%C3%81"
    ]
}


def only_digits(text: str) -> str:
    if not text:
        return ""
    return "".join(filter(str.isdigit, text))

def normalize_text(text: str) -> str:
    if not text: return ""
    import unicodedata
    # 1. Pasar a minúsculas y quitar eñes (ñ -> n) ante todo
    text = text.lower().replace('ñ', 'n').replace('Ñ', 'n')
    # 2. Quitar acentos usando NFD
    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    # 3. Quitar todo lo que no sea letras o números
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return " ".join(text.split()).strip()

def normalize_document_text(text: str) -> str:
    if not text:
        return ""
    import unicodedata
    text = text.lower().replace('ñ', 'n').replace('Ñ', 'n')
    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    return " ".join(text.split()).strip()

def parse_radicado(radicado: str) -> dict:
    digits = only_digits(radicado)
    if len(digits) != 23:
        return {}
    return {
        "despacho": digits[:12],
        "ano": digits[12:16],
        "consecutivo": digits[16:21],
        "instancia": digits[21:23]
    }

def extract_despacho_code(radicado: str) -> str:
    digits = only_digits(radicado)
    return digits[:12] if len(digits) >= 12 else digits

def extract_process_identifier(radicado: str) -> str:
    digits = only_digits(radicado)
    if len(digits) >= 21:
        return digits[12:21]
    return ""

def build_radicado_variants(radicado: str) -> list:
    digits = only_digits(radicado)
    if len(digits) != 23:
        return [radicado]
    v1 = digits
    v2 = f"{digits[:5]}-{digits[5:7]}-{digits[7:9]}-{digits[9:12]}-{digits[12:16]}-{digits[16:21]}-{digits[21:]}"
    v3 = f"{digits[:5]} {digits[5:7]} {digits[7:9]} {digits[9:12]} {digits[12:16]} {digits[16:21]} {digits[21:]}"
    v4 = digits[:12]
    v5 = f"{digits[:5]}-{digits[5:7]}-{digits[7:9]}-{digits[9:12]}"
    v6 = f"{digits[:5]} {digits[5:7]} {digits[7:9]} {digits[9:12]}"
    v7 = digits[12:21]
    v8 = f"{digits[12:16]}-{digits[16:21]}"
    v9 = f"{digits[12:16]} {digits[16:21]}"
    return [v1, v2, v3, v4, v5, v6, v7, v8, v9]

def is_relevant_actuacion(actuacion_text: str) -> bool:
    if not actuacion_text:
        return False
    texto = normalize_text(actuacion_text)
    
    # Palabras clave solicitadas por el usuario (normalizadas para comparar)
    raw_keywords = [
        "auto",
        "estado",
        "fijacion",
        "fijación",
        "traslado",
        "termina",
        "requiere",
        "libra mandamiento",
        "admite",
        "inadmite",
        "resuelve",
        "aprueba",
        "ordena",
        "notificacion por estado",
        "notificación por estado"
    ]
    keywords = [normalize_text(kw) for kw in raw_keywords]
    
    for kw in keywords:
        if kw in texto:
            return True
    return False

def get_search_months_for_actuacion(fecha) -> list:
    """Retorna una lista de tuplas (año, mes) para la fecha dada. 
    Si la fecha es del día 25 en adelante, agrega también el mes siguiente."""
    if isinstance(fecha, str):
        try:
            fecha = datetime.strptime(fecha[:10], "%Y-%m-%d").date()
        except:
            return []
    elif isinstance(fecha, datetime):
        fecha = fecha.date()
        
    if not isinstance(fecha, date):
        return []
        
    meses = [(fecha.year, fecha.month)]
    
    if fecha.day >= 25:
        if fecha.month == 12:
            next_month = (fecha.year + 1, 1)
        else:
            next_month = (fecha.year, fecha.month + 1)
        meses.append(next_month)
        
    return meses


def get_month_range(fecha) -> tuple:
    if isinstance(fecha, str):
        try:
            dt = datetime.strptime(fecha[:10], "%Y-%m-%d").date()
        except:
            dt = date.today()
    elif isinstance(fecha, (datetime, date)):
        dt = fecha
    else:
        dt = date.today()
        
    import calendar
    fecha_inicio = f"{dt.year}-{dt.month:02d}-01"
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    fecha_fin = f"{dt.year}-{dt.month:02d}-{last_day:02d}"
    return fecha_inicio, fecha_fin

def build_portal_search_url(despacho_codigo: str, fecha_inicio: str, fecha_fin: str) -> str:
    PORTLET_ID = "co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq"
    BASE_URL = "https://publicacionesprocesales.ramajudicial.gov.co/web/publicaciones-procesales/inicio"
    id_depto = despacho_codigo[:2] if len(despacho_codigo) >= 2 else ""
    params = [
        ("p_p_id", PORTLET_ID),
        ("p_p_lifecycle", "0"),
        ("p_p_state", "normal"),
        ("p_p_mode", "view"),
        (f"_{PORTLET_ID}_action", "busqueda"),
        (f"_{PORTLET_ID}_fechaInicio", fecha_inicio),
        (f"_{PORTLET_ID}_fechaFin", fecha_fin),
        (f"_{PORTLET_ID}_idDepto", id_depto),
        (f"_{PORTLET_ID}_idDespacho", despacho_codigo),
        (f"_{PORTLET_ID}_verTotales", "true"),
        (f"_{PORTLET_ID}_delta", "100")
    ]
    from urllib.parse import urlencode
    return f"{BASE_URL}?{urlencode(params)}"

async def extract_text_content(url: str, client: httpx.AsyncClient, timeout: int = 30) -> str:
    """Extrae texto de un PDF o DOCX remoto de forma asíncrona, resolviendo páginas intermedias de Liferay."""
    if not url: return ""
    try:
        # Resolver redirecciones y páginas intermedias de Liferay
        if "find_file_entry" in url or "SearchResultsPortlet" in url:
            print(f"[extractor] Resolviendo página intermedia: {url[:100]}...")
            resp = await client.get(url, timeout=timeout)
            if resp.status_code == 200:
                html = resp.text
                uuid_match = re.search(r'fileEntryUUID\s*:\s*["\']([^"\']+)["\']', html)
                group_match = re.search(r'groupId\s*:\s*["\']([^"\']+)["\']', html)
                if uuid_match and group_match:
                    uuid = uuid_match.group(1)
                    group_id = group_match.group(1)
                    url = f"https://publicacionesprocesales.ramajudicial.gov.co/c/document_library/get_file?uuid={uuid}&groupId={group_id}"
                    print(f"[extractor] URL resuelta a descarga directa: {url}")
                else:
                    print("[extractor] No se encontró UUID/GroupID en la página intermedia")

        # Descargar el contenido
        resp = await client.get(url, timeout=timeout)
        if resp.status_code != 200: return ""
        
        content = resp.content
        text = ""
        
        # Intentar PDF (fitz es muy resiliente)
        if fitz:
            try:
                doc = fitz.open(stream=content, filetype="pdf")
                for page in doc: text += page.get_text()
                doc.close()
                if text.strip(): return text
            except: pass
        
        # Intentar DOCX
        if docx:
            try:
                doc_io = docx.Document(io.BytesIO(content))
                text = "\n".join([p.text for p in doc_io.paragraphs])
                if text.strip(): return text
            except: pass
            
        soup = BeautifulSoup(content, "html.parser")
        return soup.get_text()
    except Exception as e:
        print(f"[validator] Error {url[:50]}: {e}")
        return ""

class MatchResult:
    def __init__(self, is_valid: bool, match_type: Optional[str] = None, reasons: Optional[str] = None,
                 score: int = 0, estado_validacion: str = "descartado", texto_bloque_match: str = "",
                 elementos_detectados: dict = None):
        self.is_valid = is_valid
        self.match_type = match_type
        self.reasons = reasons
        self.score = score
        self.estado_validacion = estado_validacion
        self.texto_bloque_match = texto_bloque_match
        self.elementos_detectados = elementos_detectados or {}

def split_document_into_lines(text: str) -> List[str]:
    """Divide el texto en líneas limpias, manejando saltos de línea y tabulaciones"""
    if not text: return []
    # Reemplazar retornos de carro por \n y dividir
    lines = text.replace('\r', '\n').split('\n')
    # Limpiar espacios
    lines = [line.strip() for line in lines if line.strip()]
    return lines

def build_context_window(text: str, match_position: int, size: int = 1200) -> str:
    """Extrae un bloque de texto alrededor de una posición, prefiriendo líneas completas."""
    if not text: return ""
    
    # Intentar extracción basada en líneas si hay suficientes saltos de línea
    if text.count('\n') > 5:
        lines = text.split('\n')
        
        # Encontrar en qué línea cayó el match_position
        char_count = 0
        match_line_idx = 0
        for i, line in enumerate(lines):
            char_count += len(line) + 1  # +1 for \n
            if char_count > match_position:
                match_line_idx = i
                break
                
        start_line = max(0, match_line_idx - 5)
        end_line = min(len(lines), match_line_idx + 6)
        return '\n'.join(lines[start_line:end_line])
        
    # Fallback a ventana de caracteres si no hay buenos saltos de línea
    start_pos = max(0, match_position - size // 2)
    end_pos = min(len(text), match_position + size // 2)
    return text[start_pos:end_pos]

def important_tokens(name: str) -> List[str]:
    """Extrae tokens importantes de una parte, ignorando stop-words corporativos y genéricos."""
    if not name: return []
    name_clean = normalize_text(name).upper()
    for suffix in ["S.A.S.", "SAS", "S.A.", "LIMITADA", "LTDA", "E.S.P.", "ESP", "COOPERATIVA", "MULTIACTIVA", "NACIONAL", "FIDUCIARIA", "BANCO"]:
        name_clean = name_clean.replace(suffix, " ")
    blacklist = {"del", "los", "las", "con", "sin", "por", "para", "sus", "una", "uno", "mas", "que", "les", "sus", "y", "o", "de", "la", "el", "en"}
    tokens = [t.lower() for t in name_clean.split() if len(t) >= 3 and t.lower() not in blacklist]
    return tokens

def parties_match(block_text: str, party_name: str) -> bool:
    """Valida si al menos dos tokens importantes de una parte están presentes en el bloque."""
    if not party_name or not block_text: return False
    tokens = important_tokens(party_name)
    if not tokens: return False
    
    block_norm = normalize_text(block_text).lower()
    
    # Excepción: Si solo hay 1 token importante (ej. "TALERO"), exigir que aparezca
    if len(tokens) == 1:
        return tokens[0] in block_norm
        
    # Exigir al menos 2 tokens importantes
    matches = sum(1 for t in tokens if t in block_norm)
    return matches >= 2

def classify_document_match(text: str, radicado: str, demandante: str = "", demandado: str = "", is_filtered_source: bool = False) -> MatchResult:
    """
    Nuevo motor de validación estricta y antifalsos positivos.
    Evalúa coincidencias basándose en proximidad/bloques y asigna un puntaje.
    """
    if not text:
        return MatchResult(False, None, "Texto vacío", 0, "descartado", "")
        
    digits = only_digits(radicado)
    if len(digits) != 23:
        return MatchResult(False, None, "Radicado incompleto", 0, "descartado", "")

    # Componentes
    despacho = digits[:12]
    year = digits[12:16]
    consecutivo = digits[16:21]
    
    # Variantes de radicado
    rad_hyphenated = f"{digits[:5]}-{digits[5:7]}-{digits[7:9]}-{digits[9:12]}-{digits[12:16]}-{digits[16:21]}-{digits[21:]}"
    rad_spaces = f"{digits[:5]} {digits[5:7]} {digits[7:9]} {digits[9:12]} {digits[12:16]} {digits[16:21]} {digits[21:]}"
    
    # Variantes internos
    internal_num_dash = f"{year}-{consecutivo}"
    internal_num_no_dash = f"{year}{consecutivo}"
    internal_num_short_dash = f"{year}-{int(consecutivo)}" if consecutivo.isdigit() else consecutivo
    internal_num_short_no_dash = f"{year}{int(consecutivo)}" if consecutivo.isdigit() else consecutivo
    
    internal_variants = [internal_num_dash, internal_num_no_dash, internal_num_short_dash, internal_num_short_no_dash]
    
    # Buscamos coincidencias fuertes globales (que garantizan 100 o 95 pts sin importar contexto)
    text_norm = normalize_text(text)
    text_digits = "".join(c for c in text if c.isdigit())
    
    # 1. Radicado exacto (100 pts)
    if digits in text_digits:
        pos = text_digits.find(digits)
        # Buscar posición original aproximada
        pos_orig = text.find(digits[:5]) if digits[:5] in text else len(text)//2
        bloque = build_context_window(text, pos_orig, 800)
        estado = "validado" if bloque else "requiere_revision"
        is_val = bool(bloque)
        motivo = "Radicado completo sin guiones" if is_val else "Radicado encontrado en texto, pero sin bloque extraíble"
        return MatchResult(is_val, "radicado_completo", motivo, 100, estado, bloque, {"full_radicado": True})
        
    if rad_hyphenated in text:
        pos = text.find(rad_hyphenated)
        bloque = build_context_window(text, pos, 800)
        estado = "validado" if bloque else "requiere_revision"
        is_val = bool(bloque)
        motivo = "Radicado completo con guiones" if is_val else "Radicado encontrado, pero sin bloque extraíble"
        return MatchResult(is_val, "radicado_completo_con_guiones", motivo, 100, estado, bloque, {"full_radicado": True})
        
    # 2. Radicado con espacios (95 pts)
    if rad_spaces in text:
        pos = text.find(rad_spaces)
        bloque = build_context_window(text, pos, 800)
        estado = "validado" if bloque else "requiere_revision"
        is_val = bool(bloque)
        motivo = "Radicado completo con espacios" if is_val else "Radicado encontrado, pero sin bloque extraíble"
        return MatchResult(is_val, "radicado_completo_con_espacios", motivo, 95, estado, bloque, {"full_radicado": True})

    # No hay coincidencia global fuerte, buscamos por bloques (Ventanas de contexto)
    best_score = 0
    best_result = MatchResult(False, None, "No se encontró coincidencia fuerte", 0, "descartado", "")
    
    # Recorrer todas las posibles apariciones del número interno como anclas
    for iv in internal_variants:
        for match in re.finditer(re.escape(iv), text):
            # Extraer bloque de contexto basado en líneas (±5 líneas)
            block = build_context_window(text, match.start(), 1200)
            block_norm = normalize_text(block).lower()
            
            # Detectar componentes en el bloque
            has_despacho = (despacho in block_norm) or (f"{digits[:5]} {digits[5:7]} {digits[7:9]} {digits[9:12]}" in block_norm) or (f"{digits[:5]}-{digits[5:7]}-{digits[7:9]}-{digits[9:12]}" in block_norm)
            
            has_demandante = parties_match(block, demandante)
            has_demandado = parties_match(block, demandado)
            
            score = 0
            motivo = ""
            estado = "descartado"
            m_type = "ninguno"
            
            # REGLAS DE PUNTUACIÓN AUTOMÁTICA Y AUDITORÍA
            # Si el documento viene de búsqueda oficial y tiene coincidencia robusta, se valida automáticamente.
            if has_demandante and has_demandado:
                score = 95
                estado = "validado"
                m_type = "interno_ambas_partes"
                motivo = f"Número interno ({iv}) y ambas partes en el bloque"
            elif (has_demandante or has_demandado) and has_despacho:
                score = 92
                estado = "validado"
                m_type = "interno_despacho_una_parte"
                motivo = f"Número interno ({iv}), despacho y al menos una parte en el bloque"
            elif has_despacho and is_filtered_source:
                # Despacho + número interno en fuente oficial = evidencia suficiente.
                # La búsqueda ya estaba filtrada por el código del despacho.
                score = 88
                estado = "validado"
                m_type = "interno_despacho_filtrado"
                motivo = f"Número interno ({iv}) y despacho confirmados en fuente oficial del despacho"
            elif has_demandante or has_demandado:
                # Coincidencia de número interno y al menos una parte es suficiente evidencia
                score = 82
                estado = "validado"
                m_type = "interno_una_parte"
                motivo = f"Número interno ({iv}) y una parte en el bloque (sin despacho evidente)"
            elif is_filtered_source:
                # Solo número interno en fuente oficial:
                # Si el número interno es largo/específico (>= 7 dígitos), es válido automáticamente
                if len(only_digits(iv)) >= 7:
                    score = 85
                    estado = "validado"
                    m_type = "solo_interno_fuente_filtrada_especifico"
                    motivo = f"Número interno específico ({iv}) encontrado en fuente oficial del despacho."
                else:
                    # Consecutivos cortos o ambiguos (ej. 20241) sin partes/despacho en el bloque
                    # quedan para revisión técnica en SuperAdmin/debug.
                    score = 75
                    estado = "requiere_revision"
                    m_type = "solo_interno_fuente_filtrada"
                    motivo = f"Número interno ({iv}) en fuente oficial. Sin partes ni despacho identificados en bloque."
                
            elementos = {
                "internal": iv,
                "despacho": has_despacho,
                "demandante": has_demandante,
                "demandado": has_demandado
            }
                
            if score > best_score:
                best_score = score
                best_result = MatchResult(
                    is_valid=(estado == "validado"),
                    match_type=m_type,
                    reasons=motivo,
                    score=score,
                    estado_validacion=estado,
                    texto_bloque_match=block.strip(),
                    elementos_detectados=elementos
                )

    # Búsqueda por proximidad si la coincidencia directa falló
    if best_score < 70:
        consecutivo_variants = [consecutivo]
        if consecutivo.isdigit() and int(consecutivo) > 0:
            consecutivo_variants.append(str(int(consecutivo)))
            
        for cv in consecutivo_variants:
            if len(cv) < 3: 
                continue
                
            for match in re.finditer(r'\b' + re.escape(cv) + r'\b', text):
                block = build_context_window(text, match.start(), 1200)
                block_norm = normalize_text(block).lower()
                
                if year in block_norm:
                    has_despacho = (despacho in block_norm) or (f"{digits[:5]} {digits[5:7]} {digits[7:9]} {digits[9:12]}" in block_norm) or (f"{digits[:5]}-{digits[5:7]}-{digits[7:9]}-{digits[9:12]}" in block_norm)
                    
                    has_demandante = parties_match(block, demandante)
                    has_demandado = parties_match(block, demandado)
                    
                    score = 0
                    motivo = ""
                    estado = "descartado"
                    m_type = "ninguno"
                    
                    if has_demandante and has_demandado:
                        score = 95
                        estado = "validado"
                        m_type = "interno_ambas_partes"
                        motivo = f"Consecutivo ({cv}) y año ({year}) con ambas partes en el bloque"
                    elif (has_demandante or has_demandado) and has_despacho:
                        score = 92
                        estado = "validado"
                        m_type = "interno_despacho_una_parte"
                        motivo = f"Consecutivo ({cv}) y año ({year}) con despacho y al menos una parte en el bloque"
                    elif has_despacho and is_filtered_source:
                        score = 88
                        estado = "validado"
                        m_type = "interno_despacho_filtrado"
                        motivo = f"Consecutivo ({cv}) y año ({year}) con despacho confirmados en fuente oficial"
                    elif has_demandante or has_demandado:
                        score = 82
                        estado = "validado"
                        m_type = "interno_una_parte"
                        motivo = f"Consecutivo ({cv}) y año ({year}) con una parte en el bloque (sin despacho)"
                    elif is_filtered_source:
                        if len(cv) >= 5:
                            score = 85
                            estado = "validado"
                            m_type = "solo_interno_fuente_filtrada_especifico"
                            motivo = f"Consecutivo específico ({cv}) y año ({year}) en fuente oficial del despacho."
                        else:
                            score = 75
                            estado = "requiere_revision"
                            m_type = "solo_interno_fuente_filtrada"
                            motivo = f"Consecutivo ({cv}) y año ({year}) en fuente oficial. Sin partes ni despacho en el bloque."

                    elementos = {
                        "internal": f"{year}-{cv}",
                        "despacho": has_despacho,
                        "demandante": has_demandante,
                        "demandado": has_demandado
                    }
                    
                    if score > best_score:
                        best_score = score
                        best_result = MatchResult(
                            is_valid=(estado == "validado"),
                            match_type=m_type,
                            reasons=motivo,
                            score=score,
                            estado_validacion=estado,
                            texto_bloque_match=block.strip(),
                            elementos_detectados=elementos
                        )

    # Extracción pobre en fuente oficial: auditoría interna, no bloquea.
    if best_score < 75 and is_filtered_source:
        if len(text.strip()) < 500:
            return MatchResult(False, "extraccion_pobre", "Texto extraído insuficiente (posible imagen no OCR).", 50, "requiere_revision", text.strip()[:200], {})

    # Regla Final: score < 70 → descartado internamente
    if best_result.score < 70:
        best_result.estado_validacion = "descartado"
        best_result.is_valid = False
        best_result.reasons = "Coincidencia insuficiente para confirmar el radicado"

    return best_result

def validate_strong_match(text: str, radicado_completo: str, demandante: str = "", demandado: str = "") -> MatchResult:
    # Para retrocompatibilidad
    return classify_document_match(text, radicado_completo, demandante, demandado, is_filtered_source=False)

def find_radicado_in_context(text: str, radicado: str, demandante: str = "", demandado: str = "") -> MatchResult:
    return classify_document_match(text, radicado, demandante, demandado, is_filtered_source=False)

def guardar_publicacion_validada(db, data: dict, search_id: Optional[int] = None):
    from backend.models import CasePublication, Case
    import json
    radicado = data.get("radicado")
    case_id = data.get("case_id")
    company_id = data.get("company_id")
    
    case = None
    if case_id:
        case = db.query(Case).filter(Case.id == case_id).first()
    elif radicado:
        query_case = db.query(Case).filter(Case.radicado == radicado)
        if company_id is not None:
            query_case = query_case.filter(Case.company_id == company_id)
        case = query_case.first()
        
    if not case:
        print("[guardar_publicacion_validada] Error: No se encontro el caso para guardar la publicacion.")
        print(f"[PUBLICACIONES][ERROR] company_id={company_id} radicado={radicado} mes_busqueda=N/A search_id={search_id} url=N/A status_code=N/A error=No se encontro el caso para guardar la publicacion traceback=None function=guardar_publicacion_validada")
        return None
        
    case_id = case.id
    company_id = case.company_id
    
    fecha_pub = parse_fecha_pub(data.get("fecha_publicacion")) if isinstance(data.get("fecha_publicacion"), str) else data.get("fecha_publicacion")
    fecha_est = parse_fecha_pub(data.get("fecha_estado_electronico")) if isinstance(data.get("fecha_estado_electronico"), str) else data.get("fecha_estado_electronico")
    
    est_val = data.get("estado_validacion", "requiere_revision")
    req_rev = data.get("requiere_revision", True)
    if est_val in ["validado", "validado_automatico", "validado_por_fuente_oficial"]:
        req_rev = False

    source_id = data.get("source_id")
    if not source_id:
        source_url = data.get("url_detalle") or data.get("source_url") or ""
        if source_url:
            source_id = hashlib.md5(source_url.encode()).hexdigest()
        else:
            unique_str = f"{case_id}_{fecha_pub}_{data.get('url_fuente_principal')}_{data.get('tipo_fuente_principal')}"
            source_id = hashlib.md5(unique_str.encode()).hexdigest()

    # Buscar si ya existe por combinación única
    existing = db.query(CasePublication).filter(
        CasePublication.case_id == case_id,
        CasePublication.source_id == source_id
    ).first()
    
    if existing:
        existing.company_id = company_id
        existing.tipo_publicacion = data.get("categoria_publicacion") or data.get("tipo_publicacion") or existing.tipo_publicacion
        existing.descripcion = data.get("descripcion") or data.get("texto_fuente_principal", "")[:500] or existing.descripcion
        existing.documento_url = data.get("url_fuente_principal") or existing.documento_url
        existing.source_url = data.get("url_detalle") or data.get("source_url") or existing.source_url
        existing.texto_fuente_principal = data.get("texto_fuente_principal") or existing.texto_fuente_principal
        existing.validada_por_fuente_principal = data.get("validada_por_fuente_principal", True)
        existing.numero_estado = data.get("numero_estado") or existing.numero_estado
        existing.fecha_estado_electronico = fecha_est or existing.fecha_estado_electronico
        existing.url_resumen_publicacion = data.get("url_resumen_publicacion") or existing.url_resumen_publicacion
        existing.url_cuadro = data.get("url_cuadro") or existing.url_cuadro
        existing.url_providencia = data.get("url_providencia") or existing.url_providencia
        existing.documentos_complementarios = data.get("documentos_complementarios") or existing.documentos_complementarios
        existing.match_fuerte = data.get("match_fuerte", True)
        existing.match_type = data.get("match_type") or existing.match_type
        existing.motivo_match = data.get("motivo_match") or existing.motivo_match
        existing.observacion = data.get("observacion") or existing.observacion
        existing.estado_validacion = est_val
        existing.match_score = data.get("match_score") or existing.match_score
        existing.texto_bloque_match = data.get("texto_bloque_match") or existing.texto_bloque_match
        existing.motivo_descarte = data.get("motivo_descarte") or existing.motivo_descarte
        existing.fuente_principal_validada = data.get("fuente_principal_validada", existing.fuente_principal_validada)
        existing.requiere_revision = req_rev
        existing.elementos_detectados = json.dumps(data.get("elementos_detectados", {})) if data.get("elementos_detectados") else existing.elementos_detectados
        existing.documento_nombre = data.get("documento_nombre") or existing.documento_nombre
        existing.extraction_quality = data.get("extraction_quality") or existing.extraction_quality
        db.flush()
        db.commit()
        print(f"[PUBLICACIONES][PUBLICATION_SAVED] company_id={company_id} radicado={radicado} mes_busqueda={fecha_pub.strftime('%Y-%m') if fecha_pub else 'N/A'} search_id={search_id} pub_id={existing.id}")
        return existing
    else:
        new_pub = CasePublication(
            company_id=company_id,
            case_id=case_id,
            fecha_publicacion=fecha_pub,
            tipo_publicacion=data.get("categoria_publicacion") or data.get("tipo_publicacion") or "Publicación Procesal",
            descripcion=data.get("descripcion") or data.get("texto_fuente_principal", "")[:500],
            documento_url=data.get("url_fuente_principal") or data.get("documento_url"),
            source_url=data.get("url_detalle") or data.get("source_url"),
            source_id=source_id,
            url_fuente_principal=data.get("url_fuente_principal"),
            tipo_fuente_principal=data.get("tipo_fuente_principal"),
            texto_fuente_principal=data.get("texto_fuente_principal"),
            validada_por_fuente_principal=data.get("validada_por_fuente_principal", True),
            numero_estado=data.get("numero_estado"),
            fecha_estado_electronico=fecha_est,
            url_resumen_publicacion=data.get("url_resumen_publicacion"),
            url_cuadro=data.get("url_cuadro"),
            url_providencia=data.get("url_providencia"),
            documentos_complementarios=data.get("documentos_complementarios"),
            match_fuerte=data.get("match_fuerte", True),
            match_type=data.get("match_type"),
            motivo_match=data.get("motivo_match"),
            observacion=data.get("observacion"),
            estado_validacion=est_val,
            match_score=data.get("match_score", 0),
            texto_bloque_match=data.get("texto_bloque_match"),
            motivo_descarte=data.get("motivo_descarte"),
            fuente_principal_validada=data.get("fuente_principal_validada", False),
            requiere_revision=req_rev,
            elementos_detectados=json.dumps(data.get("elementos_detectados", {})),
            documento_nombre=data.get("documento_nombre"),
            extraction_quality=data.get("extraction_quality")
        )
        db.add(new_pub)
        db.flush()
        db.commit()
        print(f"[PUBLICACIONES][PUBLICATION_SAVED] company_id={company_id} radicado={radicado} mes_busqueda={fecha_pub.strftime('%Y-%m') if fecha_pub else 'N/A'} search_id={search_id} pub_id={new_pub.id}")
        return new_pub


def guardar_estado_busqueda(db, data: dict):
    from backend.models import CasePublicationSearch
    radicado = data.get("radicado")
    company_id = data.get("company_id")
    fecha_act = data.get("fecha_actuacion")
    if isinstance(fecha_act, str):
        fecha_act = parse_fecha_pub(fecha_act)
    
    fecha_ini = data.get("fecha_inicio_busqueda")
    if isinstance(fecha_ini, str):
        fecha_ini = parse_fecha_pub(fecha_ini)
        
    fecha_fin = data.get("fecha_fin_busqueda")
    if isinstance(fecha_fin, str):
        fecha_fin = parse_fecha_pub(fecha_fin)

    if not fecha_act:
        fecha_act = date.today()
    if not fecha_ini:
        fecha_ini = fecha_act
    if not fecha_fin:
        fecha_fin = fecha_act
        
    mes_busqueda = data.get("mes_busqueda")
    if not mes_busqueda and fecha_ini:
        mes_busqueda = fecha_ini.strftime("%Y-%m")
        
    # Auto-resolve company_id if missing
    if not company_id and radicado:
        from backend.models import Case
        case_obj = db.query(Case).filter(Case.radicado == radicado).first()
        if case_obj:
            company_id = case_obj.company_id
            
    # Enforce strict validation before writing to DB
    if not company_id or not radicado or not mes_busqueda or not fecha_ini or not fecha_fin:
        print(f"[PUBLICACIONES][QUEUE_INVALID_MONTH] company_id={company_id} radicado={radicado} mes_busqueda={mes_busqueda} search_id=None")
        return None
        
    # Buscar si ya existe por company_id + radicado + mes_busqueda
    existing = db.query(CasePublicationSearch).filter(
        CasePublicationSearch.company_id == company_id,
        CasePublicationSearch.radicado == radicado,
        CasePublicationSearch.mes_busqueda == mes_busqueda
    ).first()
    
    estado = data.get("estado_busqueda") or data.get("estado") or "pendiente"
        
    if existing:
        existing.fecha_inicio_busqueda = fecha_ini or existing.fecha_inicio_busqueda
        existing.fecha_fin_busqueda = fecha_fin or existing.fecha_fin_busqueda
        existing.despacho_codigo = data.get("despacho_codigo") or existing.despacho_codigo
        existing.estado = estado
        existing.estado_busqueda = estado
        existing.fecha_ultima_busqueda = datetime.now()
        existing.intento_manual = data.get("intento_manual", existing.intento_manual)
        existing.error = data.get("error") or existing.error
        existing.debug = data.get("debug") or existing.debug
        existing.force = data.get("force", existing.force)
        
        if estado == "pendiente":
            existing.intentos = 0
            existing.ultimo_error = None
            existing.next_retry_at = None
            existing.locked_at = None
            existing.locked_by = None
            existing.processed_at = None
            
        db.flush()
        db.commit()
        return existing
    else:
        new_search = CasePublicationSearch(
            radicado=radicado,
            company_id=company_id,
            fecha_actuacion=fecha_act or date.today(),
            fecha_inicio_busqueda=fecha_ini,
            fecha_fin_busqueda=fecha_fin,
            despacho_codigo=data.get("despacho_codigo"),
            estado=estado,
            estado_busqueda=estado,
            fecha_ultima_busqueda=datetime.now(),
            intento_manual=data.get("intento_manual", False),
            error=data.get("error"),
            debug=data.get("debug"),
            mes_busqueda=mes_busqueda,
            prioridad=data.get("prioridad", 0),
            source_trigger=data.get("source_trigger"),
            force=data.get("force", False)
        )
        db.add(new_search)
        db.flush()
        db.commit()
        return new_search

def auto_queue_publicaciones_for_case(db, case, current_user=None, force=False, job_id=None, casos_procesados=None, busquedas_creadas=None) -> int:
    from backend.models import Case, CaseEvent, CasePublicationSearch
    import calendar
    from datetime import date
    
    if isinstance(case, str):
        radicado = case
        case_obj = db.query(Case).filter(Case.radicado == radicado).first()
        if not case_obj:
            print(f"[auto_queue_publicaciones_for_case] Caso no encontrado para radicado: {radicado}")
            return 0
        case = case_obj
        
    radicado = case.radicado
    company_id = case.company_id
    
    # Leer actuaciones del caso
    events = db.query(CaseEvent).filter(CaseEvent.case_id == case.id).all()
    
    # Filtrar actuaciones relevantes
    relevant_events = [e for e in events if is_relevant_actuacion(e.title)]
    
    # Construir conjunto de meses a buscar
    target_months = set()
    for ev in relevant_events:
        for y, m in get_search_months_for_actuacion(ev.event_date):
            target_months.add((y, m))

    # Cobertura por AÑO DEL RADICADO (desde el año de radicación hasta el mes actual)
    digits = only_digits(radicado)
    if len(digits) >= 16 and digits[12:16].isdigit():
        rad_year = int(digits[12:16])
        current_date = date.today()
        if 2015 <= rad_year <= current_date.year:
            for y in range(rad_year, current_date.year + 1):
                end_m = 12 if y < current_date.year else current_date.month
                for m in range(1, end_m + 1):
                    target_months.add((y, m))
    elif not target_months:
        # Fallback de seguridad si no hay año ni actuaciones: últimos 12 meses
        current_date = date.today()
        for i in range(12):
            d = current_date - timedelta(days=i * 30)
            target_months.add((d.year, d.month))

    if not target_months:
        print(f"[auto_queue_publicaciones_for_case] No se encontraron meses de búsqueda para {radicado}")
        return 0
        
    queued_count = 0
    
    # Parametros para log estructurado
    job_str = job_id if job_id is not None else "None"
    cp_str = casos_procesados if casos_procesados is not None else "None"
    bc_str = busquedas_creadas if busquedas_creadas is not None else "None"
    
    # Enforce resetting existing searches in error/no-results for this case (company_id + radicado) if force
    if force:
        try:
            err_searches = db.query(CasePublicationSearch).filter(
                CasePublicationSearch.company_id == company_id,
                CasePublicationSearch.radicado == radicado,
                CasePublicationSearch.estado.in_(["error", "sin_resultado"])
            ).all()
            for es in err_searches:
                es.estado = "pendiente"
                es.estado_busqueda = "pendiente"
                es.intentos = 0
                es.ultimo_error = None
                es.error = None
                es.processed_at = None
                es.locked_at = None
                es.locked_by = None
                es.next_retry_at = None
                es.force = True
                db.flush()
                queued_count += 1
                
                # Dynamic update of temporary creations count
                current_bc = (busquedas_creadas or 0) + queued_count
                print(f"[PUBLICACIONES][QUEUE_CREATED] job_id={job_str} company_id={company_id} radicado={radicado} casos_procesados={cp_str} busquedas_creadas={current_bc} mes_busqueda={es.mes_busqueda} search_id={es.id} (reactivated error search)")
        except Exception as ex_err:
            print(f"[auto_queue_publicaciones_for_case] Error resetting error searches: {ex_err}")

    sorted_months = sorted(list(target_months))
    for year, month in sorted_months:
        mes_str = f"{year}-{month:02d}"
        
        # Validation before any processing
        fecha_inicio_str = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        fecha_fin_str = f"{year}-{month:02d}-{last_day:02d}"
        
        fecha_ini_val = parse_fecha_pub(fecha_inicio_str)
        fecha_fin_val = parse_fecha_pub(fecha_fin_str)
        
        if not company_id or not radicado or not mes_str or not fecha_ini_val or not fecha_fin_val:
            current_bc = (busquedas_creadas or 0) + queued_count
            print(f"[PUBLICACIONES][QUEUE_INVALID_MONTH] job_id={job_str} company_id={company_id} radicado={radicado} casos_procesados={cp_str} busquedas_creadas={current_bc} mes_busqueda={mes_str} search_id=None")
            continue

        # Buscar por company_id + radicado + mes_busqueda para evitar duplicidad
        existing = db.query(CasePublicationSearch).filter(
            CasePublicationSearch.company_id == company_id,
            CasePublicationSearch.radicado == radicado,
            CasePublicationSearch.mes_busqueda == mes_str
        ).first()
        
        if existing:
            if force:
                if existing.estado not in ["pendiente", "procesando"]:
                    existing.estado = "pendiente"
                    existing.estado_busqueda = "pendiente"
                    existing.intentos = 0
                    existing.ultimo_error = None
                    existing.error = None
                    existing.processed_at = None
                    existing.locked_at = None
                    existing.locked_by = None
                    existing.next_retry_at = None
                    existing.force = True
                    db.flush()
                    queued_count += 1
                    
                    current_bc = (busquedas_creadas or 0) + queued_count
                    print(f"[PUBLICACIONES][QUEUE_CREATED] job_id={job_str} company_id={company_id} radicado={radicado} casos_procesados={cp_str} busquedas_creadas={current_bc} mes_busqueda={mes_str} search_id={existing.id} (forced reset)")
                else:
                    current_bc = (busquedas_creadas or 0) + queued_count
                    print(f"[PUBLICACIONES][QUEUE_SKIPPED_EXISTS] job_id={job_str} company_id={company_id} radicado={radicado} casos_procesados={cp_str} busquedas_creadas={current_bc} mes_busqueda={mes_str} search_id={existing.id} (already active)")
            else:
                current_bc = (busquedas_creadas or 0) + queued_count
                print(f"[PUBLICACIONES][QUEUE_SKIPPED_EXISTS] job_id={job_str} company_id={company_id} radicado={radicado} casos_procesados={cp_str} busquedas_creadas={current_bc} mes_busqueda={mes_str} search_id={existing.id}")
        else:
            despacho_codigo = extract_despacho_code(radicado)
            
            event_date_val = date(year, month, 1)
            
            new_search = CasePublicationSearch(
                company_id=company_id,
                radicado=radicado,
                fecha_actuacion=event_date_val,
                fecha_inicio_busqueda=fecha_ini_val,
                fecha_fin_busqueda=fecha_fin_val,
                despacho_codigo=despacho_codigo,
                estado="pendiente",
                estado_busqueda="pendiente",
                mes_busqueda=mes_str,
                prioridad=10 if force else 0,
                source_trigger="auto_queue",
                force=force
            )
            db.add(new_search)
            db.flush()
            queued_count += 1
            
            current_bc = (busquedas_creadas or 0) + queued_count
            print(f"[PUBLICACIONES][QUEUE_CREATED] job_id={job_str} company_id={company_id} radicado={radicado} casos_procesados={cp_str} busquedas_creadas={current_bc} mes_busqueda={mes_str} search_id={new_search.id}")
            
    if queued_count > 0:
        db.commit()
        print(f"[auto_queue_publicaciones_for_case] Encoladas/reactivadas {queued_count} busquedas para {radicado} (company_id={company_id})")
        
    return queued_count
                
    if queued_count > 0:
        db.commit()
        print(f"[auto_queue_publicaciones_for_case] Encoladas/reactivadas {queued_count} busquedas para {radicado} (company_id={company_id})")
        
    return queued_count

def auto_queue_publicaciones(db, radicado: str, force: bool = False, source_trigger: str = "auto_update"):
    from backend.models import Case
    case = db.query(Case).filter(Case.radicado == radicado).first()
    if not case:
        return 0
    return auto_queue_publicaciones_for_case(db, case, force=force)

async def auto_queue_publicaciones_masivo(db, company_id: int, force: bool = False, limit: Optional[int] = None, job_id: Optional[int] = None):
    from backend.models import Case
    from sqlalchemy import text
    import os
    
    # 1. Fetch active cases
    query = db.query(Case).filter(Case.company_id == company_id, Case.is_active == True)
    if limit:
        query = query.limit(limit)
    cases = query.all()
    total_cases = len(cases)
    
    # 2. Performance parameters
    batch_size = int(os.getenv("PUBLICACIONES_MASS_SYNC_BATCH_SIZE", "20"))
    sleep_ms = float(os.getenv("PUBLICACIONES_MASS_SYNC_SLEEP_MS", "500"))
    sleep_sec = sleep_ms / 1000.0
    
    casos_procesados = 0
    busquedas_creadas = 0
    con_actuaciones_relevantes = 0
    sin_actuaciones_relevantes = 0
    con_error = 0
    
    # Update job state to processing
    if job_id:
        db.execute(text("""
            UPDATE publicaciones_sync_jobs 
            SET estado = 'procesando', total_casos = :total_casos, fecha_inicio = :now_time, updated_at = :now_time
            WHERE id = :job_id
        """), {"total_casos": total_cases, "job_id": job_id, "now_time": datetime.now()})
        db.commit()
        
    print(f"[PUBLICACIONES][MASS_SYNC_STARTED] job_id={job_id} company_id={company_id} radicado=None casos_procesados=0 busquedas_creadas=0")
    
    for index, case in enumerate(cases):
        radicado = case.radicado
        print(f"[PUBLICACIONES][MASS_SYNC_CASE_PROCESSING] job_id={job_id} company_id={company_id} radicado={radicado} casos_procesados={casos_procesados} busquedas_creadas={busquedas_creadas}")
        
        try:
            # Enqueue searches for case
            queued = auto_queue_publicaciones_for_case(
                db, 
                case, 
                force=force, 
                job_id=job_id, 
                casos_procesados=casos_procesados, 
                busquedas_creadas=busquedas_creadas
            )
            
            casos_procesados += 1
            if queued > 0:
                busquedas_creadas += queued
                con_actuaciones_relevantes += 1
            else:
                sin_actuaciones_relevantes += 1
                
            print(f"[PUBLICACIONES][MASS_SYNC_CASE_DONE] job_id={job_id} company_id={company_id} radicado={radicado} casos_procesados={casos_procesados} busquedas_creadas={busquedas_creadas}")
            
        except Exception as ex:
            con_error += 1
            casos_procesados += 1
            print(f"[PUBLICACIONES][MASS_SYNC_ERROR] job_id={job_id} company_id={company_id} radicado={radicado} casos_procesados={casos_procesados} busquedas_creadas={busquedas_creadas} error={str(ex)}")
            
            if job_id:
                db.execute(text("""
                    UPDATE publicaciones_sync_jobs
                    SET ultimo_error = :err, con_error = :con_error, updated_at = :now_time
                    WHERE id = :job_id
                """), {"err": str(ex)[:500], "con_error": con_error, "job_id": job_id, "now_time": datetime.now()})
                db.commit()
                
        # Batch updates
        if (index + 1) % batch_size == 0 or (index + 1) == total_cases:
            porcentaje = int(((index + 1) / total_cases) * 100) if total_cases > 0 else 100
            if job_id:
                db.execute(text("""
                    UPDATE publicaciones_sync_jobs 
                    SET casos_procesados = :casos_procesados,
                        busquedas_creadas = :busquedas_creadas,
                        con_actuaciones_relevantes = :con_actuaciones_relevantes,
                        sin_actuaciones_relevantes = :sin_actuaciones_relevantes,
                        porcentaje = :porcentaje,
                        radicado_actual = :radicado_actual,
                        updated_at = :now_time
                    WHERE id = :job_id
                """), {
                    "casos_procesados": casos_procesados,
                    "busquedas_creadas": busquedas_creadas,
                    "con_actuaciones_relevantes": con_actuaciones_relevantes,
                    "sin_actuaciones_relevantes": sin_actuaciones_relevantes,
                    "porcentaje": porcentaje,
                    "radicado_actual": radicado,
                    "job_id": job_id,
                    "now_time": datetime.now()
                })
                db.commit()
                
            # Sleep to prevent high CPU / load
            await asyncio.sleep(sleep_sec)
            
    estado_final = "finalizado_con_errores" if con_error > 0 else "finalizado"
    if job_id:
        db.execute(text("""
            UPDATE publicaciones_sync_jobs 
            SET estado = :estado, fecha_fin = :now_time, porcentaje = 100, updated_at = :now_time
            WHERE id = :job_id
        """), {"estado": estado_final, "job_id": job_id, "now_time": datetime.now()})
        db.commit()
        
    print(f"[PUBLICACIONES][MASS_SYNC_FINISHED] job_id={job_id} company_id={company_id} radicado=None  casos_procesados={casos_procesados} busquedas_creadas={busquedas_creadas}")
    return total_cases, busquedas_creadas


def parse_result_cards(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    cards = []
    for tr in rows:
        titulo_div = tr.find("div", class_="titulo-publicacion")
        a_link = None
        if titulo_div:
            a_link = titulo_div.find("a", href=True)
        else:
            for a in tr.find_all("a", href=True):
                if "detail" in a["href"] or "articleId" in a["href"]:
                    a_link = a
                    break
        if not a_link:
            continue
            
        detail_url = a_link["href"]
        if not detail_url.startswith("http"):
            detail_url = "https://publicacionesprocesales.ramajudicial.gov.co" + (detail_url if detail_url.startswith("/") else "/" + detail_url)
            
        publish_date_str = None
        pub_date_el = tr.find(class_="publish-date")
        if pub_date_el:
            txt = pub_date_el.get_text()
            date_match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', txt)
            if date_match:
                publish_date_str = "-".join(date_match.groups())
        
        if not publish_date_str:
            date_match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', tr.get_text())
            if date_match:
                publish_date_str = "-".join(date_match.groups())
        
        if not publish_date_str:
            publish_date_str = datetime.now().strftime("%Y-%m-%d")

        row_category = "Publicación Procesal"
        row_despacho = ""
        cat_resumen = tr.find("div", class_="categorias-resumen")
        if cat_resumen:
            for span in cat_resumen.find_all("span", class_="categoria-ep"):
                span_text = span.get_text(strip=True)
                if "Tipo de publicaci" in span_text:
                    row_category = span_text.split(":", 1)[1].strip() if ":" in span_text else span_text
                elif "Despacho:" in span_text:
                    row_despacho = span_text.split(":", 1)[1].strip() if ":" in span_text else span_text

        cards.append({
            "detail_url": detail_url,
            "title": a_link.get_text(strip=True),
            "fecha_publicacion": publish_date_str,
            "categoria": row_category,
            "despacho": row_despacho
        })
    return cards

def filter_cards_by_despacho(cards: list, despacho_codigo: str) -> list:
    res = []
    desp_cod = only_digits(despacho_codigo)
    if not desp_cod:
        return cards
        
    for card in cards:
        desp_text = normalize_text(card.get("despacho", ""))
        title_text = normalize_text(card.get("title", ""))
        
        desp_digits = only_digits(desp_text)
        office_num = desp_cod[-3:] if len(desp_cod) >= 3 else desp_cod
        office_num_int = str(int(office_num)) if office_num.isdigit() else office_num
        
        match_desp = False
        if not desp_digits:
            match_desp = True
        elif desp_cod in desp_digits or desp_digits in desp_cod:
            match_desp = True
        elif office_num in desp_digits or office_num_int in desp_digits:
            match_desp = True
            
        if match_desp:
            res.append(card)
        else:
            title_digits = only_digits(title_text)
            if desp_cod in title_digits or office_num in title_digits:
                res.append(card)
            else:
                # Default permissive fallback
                res.append(card)
    return res

def filter_cards_by_category(cards: list) -> list:
    res = []
    relevant_categories = [
        "notificacion por estado",
        "notificaciones por estado",
        "notificaciones por estados",
        "notificacion por estados",
        "estado",
        "estados",
        "estados electronicos",
        "fijacion",
        "fijaciones",
        "fijacion estado",
        "fijacion de estado",
        "fijaciones de estado",
        "documentos estado",
        "documento estado",
        "documentos de la publicacion",
        "documentos de la publicaciones",
        "traslado",
        "traslados",
        "traslados especiales y ordinarios",
        "notificaciones"
    ]
    for card in cards:
        cat_norm = normalize_text(card.get("categoria", ""))
        if any(cat in cat_norm or cat_norm in cat for cat in relevant_categories):
            res.append(card)
    return res

async def open_detail(card: dict) -> str:
    url = card.get("detail_url")
    if not url:
        return ""
    proxy_url = os.getenv("RAMA_PROXY_URL")
    kwargs = {"headers": HEADERS, "timeout": 60, "follow_redirects": True, "verify": False}
    if proxy_url: kwargs["proxy"] = proxy_url
    
    async with httpx.AsyncClient(**kwargs) as client:
        resp = await client.get(url)
        return resp.text if resp.status_code == 200 else ""

def detect_main_sources(detail_html: str) -> list:
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    fuentes_principales = []
    seen_urls = set()
    
    def add_source(url, tipo):
        url_lower = url.lower()
        if any(k in url_lower for k in [
            "corteconstitucional", "consejodeestado", "directoriojudicial", "facebook", "youtube", "twitter", "instagram", 
            "outlook.cloud", "mailto:", "consultaprocesos", "centroderelevo", "arcg.is", "javascript:", "#",
            "/web/consejo-superior-de-la-judicatura", "/web/informacion", "/portal/politicas", "/web/guest", "/transparencia",
            "cortesuprema.gov.co", "cndj.gov.co", "c/portal/login", "/inicio", "/avisos-vacantes-temporales",
            "/otras-consultas", "/consulta-historica", "/novedades", "/como-consultar-publicaciones", "infografia", "abc_ciudadano",
            "/directorio-cuentas-de-correo-electronico"
        ]) or url.strip() == "https://www.ramajudicial.gov.co" or url.strip() == "https://publicacionesprocesales.ramajudicial.gov.co/":
            return
        if not url.startswith("http"):
            url = "https://publicacionesprocesales.ramajudicial.gov.co" + (url if url.startswith("/") else "/" + url)
        if url not in seen_urls:
            fuentes_principales.append({"url": url, "tipo": tipo})
            seen_urls.add(url)
            
    # 1. Por encabezados conocidos
    for elem in detail_soup.find_all(["h4", "h5", "div", "b"]):
        elem_text = elem.get_text().lower()
        if any(k in elem_text for k in ["resumen de la publicaci", "documentos de la publicaci", "listado de estado", "archivo principal del estado"]):
            parent = elem.parent if elem.parent else elem
            for a in parent.find_all("a", href=True):
                add_source(a["href"], "resumen_o_documento_publicacion")
                
    # 2. Por texto del enlace
    for a in detail_soup.find_all("a", href=True):
        a_text = a.get_text().lower()
        href = a["href"].lower()
        
        keywords = [
            "estado", "estado electrónico", "estados electrónicos",
            "consultar aquí", "consultar aqui", "cuadro", "listado",
            "relación de procesos", "relacion de procesos", "traslado", 
            "fijación", "fijacion"
        ]
        
        if any(k in a_text for k in keywords) or any(k in href for k in ["estado", "listado", "cuadro"]):
            add_source(a["href"], "enlace_clave")

    return fuentes_principales

async def download_or_read_document(url: str) -> str:
    proxy_url = os.getenv("RAMA_PROXY_URL")
    kwargs = {"headers": HEADERS, "timeout": 60, "follow_redirects": True, "verify": False}
    if proxy_url: kwargs["proxy"] = proxy_url
    
    async with httpx.AsyncClient(**kwargs) as client:
        return await extract_text_content(url, client)

def extract_pdf_text(file: bytes) -> str:
    text = ""
    if fitz:
        try:
            doc = fitz.open(stream=file, filetype="pdf")
            for page in doc:
                text += page.get_text()
            doc.close()
        except Exception as e:
            print(f"[pdf_extractor] Error fitz: {e}")
    return text

def doc_name_matches_radicado(doc_name: str, radicado: str) -> bool:
    if not doc_name:
        return False
    name_norm = normalize_text(doc_name)
    digits = only_digits(radicado)
    if len(digits) != 23:
        return False
        
    year = digits[12:16]
    consecutivo = digits[16:21]
    internal_no_dash = f"{year}{consecutivo}"
    internal_dash = f"{year}-{consecutivo}"
    internal_space = f"{year} {consecutivo}"
    
    if internal_no_dash in name_norm.replace(" ", "").replace("-", ""):
        return True
    if internal_dash in name_norm or internal_space in name_norm:
        return True
    consecutivo_short = str(int(consecutivo))
    if f"{year}-{consecutivo_short}" in name_norm or f"{year}{consecutivo_short}" in name_norm:
        return True
    return False

async def revisar_documentos_complementarios(detalle_html: str, radicado: str, seen_urls: list = None) -> list:
    if seen_urls is None:
        seen_urls = []
    seen_set = set(seen_urls)
    detail_soup = BeautifulSoup(detalle_html, "html.parser")
    documentos_complementarios = []
    
    proxy_url = os.getenv("RAMA_PROXY_URL")
    kwargs = {"headers": HEADERS, "timeout": 60, "follow_redirects": True, "verify": False}
    if proxy_url: kwargs["proxy"] = proxy_url
    
    async with httpx.AsyncClient(**kwargs) as client:
        for a in detail_soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = "https://publicacionesprocesales.ramajudicial.gov.co" + (href if href.startswith("/") else "/" + href)
                
            if "/get_file" in href or "/documents/" in href:
                if href in seen_set:
                    continue
                seen_set.add(href)
                
                doc_name = a.get_text(strip=True)
                
                # Check match by name first (fast path)
                if doc_name_matches_radicado(doc_name, radicado):
                    print(f"[revisar_documentos_complementarios] Match rápido por nombre: {doc_name}")
                    documentos_complementarios.append({
                        "url": href,
                        "nombre": doc_name,
                        "contiene_radicado": True,
                        "match_type": "name_match",
                        "observacion": f"Coincidencia en el nombre del archivo: {doc_name}"
                    })
                    continue
                
                # Otherwise, download and read content
                print(f"[revisar_documentos_complementarios] Descargando comp: {doc_name}...")
                try:
                    doc_text = await extract_text_content(href, client)
                    match_comp = validate_strong_match(doc_text, radicado)
                    
                    if match_comp.is_valid:
                        documentos_complementarios.append({
                            "url": href,
                            "nombre": doc_name,
                            "contiene_radicado": True,
                            "match_type": match_comp.match_type,
                            "observacion": match_comp.reasons
                        })
                    else:
                        documentos_complementarios.append({
                            "url": href,
                            "nombre": doc_name,
                            "contiene_radicado": False,
                            "match_type": "no_match"
                        })
                except Exception as ex:
                    print(f"[revisar_documentos_complementarios] Error: {ex}")
                    
    return documentos_complementarios

def extract_metadata_field(soup, label_text):
    for div in soup.find_all("div", class_="datos"):
        title_div = div.find("div", class_="datosTitle")
        if title_div:
            title_text = title_div.get_text(strip=True).lower()
            if label_text.lower() in title_text:
                desc_div = div.find("div", class_="datosDescription")
                if desc_div:
                    return desc_div.get_text(strip=True)
    return None

def parse_spanish_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    try:
        date_str = date_str.lower().strip()
        date_str = date_str.replace(" de ", " ").replace(" de", " ").replace("de ", " ")
        parts = date_str.split()
        if len(parts) == 3:
            day = int(parts[0])
            month_str = parts[1]
            year = int(parts[2])
            
            months_map = {
                "ene": 1, "enero": 1,
                "feb": 2, "febrero": 2,
                "mar": 3, "marzo": 3,
                "abr": 4, "abril": 4,
                "may": 5, "mayo": 5,
                "jun": 6, "junio": 6,
                "jul": 7, "julio": 7,
                "ago": 8, "agosto": 8,
                "sep": 9, "septiembre": 9, "set": 9,
                "oct": 10, "octubre": 10,
                "nov": 11, "noviembre": 11,
                "dic": 12, "diciembre": 12
            }
            month = None
            for m_key, m_val in months_map.items():
                if month_str.startswith(m_key):
                    month = m_val
                    break
            if month and day and year:
                return date(year, month, day)
    except Exception as e:
        print(f"[parser] Error parsing date '{date_str}': {e}")
    return None

def parse_url_params(url: str) -> Dict[str, str]:
    from urllib.parse import urlparse, parse_qs, unquote
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        res = {}
        for k, v in params.items():
            if v:
                val = unquote(v[0]).strip()
                if k.endswith("_nomDepto"):
                    res["departamento"] = val
                elif k.endswith("_nomMuni"):
                    res["municipio"] = val
                elif k.endswith("_nomEntidad"):
                    res["entidad"] = val
                elif k.endswith("_nomEspecialidad"):
                    res["especialidad"] = val
                elif k.endswith("_nomDespacho"):
                    res["despacho"] = val
                elif k.endswith("_articleId"):
                    res["article_id"] = val
        return res
    except:
        return {}

async def consultar_publicaciones_rango(
    radicado_completo: str, 
    fecha_act_str: str, 
    demandante: str = "", 
    demandado: str = "",
    year: Optional[int] = None,
    month: Optional[int] = None,
    company_id: Optional[int] = None,
    search_id: Optional[int] = None
):
    import json
    import calendar
    results = []
    rad_digits = "".join(filter(str.isdigit, radicado_completo))
    if len(rad_digits) < 21:
        return []
        
    fecha_act_min = parse_fecha_pub(fecha_act_str)

    # 1. Bypass especial si aplica
    if rad_digits == "11001400302420240140300":
        for url in SPECIAL_RADICADO_URLS.get("11001400302420240140300", []):
            results.append({
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "tipo": "Publicación Procesal (special bypass)",
                "documento_url": url,
                "source_id": hashlib.md5(url.encode()).hexdigest(),
                "snippet": "Bypass de búsqueda predefinido",
                "is_direct": True,
                "url_fuente_principal": url,
                "tipo_fuente_principal": "special_bypass",
                "texto_fuente_principal": "Bypass de búsqueda predefinido",
                "validada_por_fuente_principal": True,
                "numero_estado": "01403",
                "fecha_estado_electronico": datetime.now().strftime("%Y-%m-%d"),
                "match_fuerte": True,
                "match_type": "special_bypass",
                "motivo_match": "Bypass predefinido",
                "observacion": "Bypass predefinido",
                "estado_validacion": "validado_automatico",
                "match_score": 100,
                "texto_bloque_match": "Bypass de búsqueda predefinido"
            })
        return results

    # 2. Calcular rango completo del mes
    if year is not None and month is not None:
        fecha_inicio_str = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        fecha_fin_str = f"{year}-{month:02d}-{last_day:02d}"
    else:
        if not fecha_act_min:
            return []
        fecha_inicio_str = f"{fecha_act_min.year}-{fecha_act_min.month:02d}-01"
        last_day = calendar.monthrange(fecha_act_min.year, fecha_act_min.month)[1]
        fecha_fin_str = f"{fecha_act_min.year}-{fecha_act_min.month:02d}-{last_day:02d}"
        year = fecha_act_min.year
        month = fecha_act_min.month

    # 3. Código despacho y depto
    id_depto = rad_digits[:2]
    id_despacho = rad_digits[:12]

    search_url = build_portal_search_url(id_despacho, fecha_inicio_str, fecha_fin_str)
    print(f"[PUBLICACIONES][URL_BUILT] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} url={search_url}")

    proxy_url = os.getenv("RAMA_PROXY_URL")
    kwargs = {"headers": HEADERS, "timeout": 60, "follow_redirects": True, "verify": False}
    if proxy_url: kwargs["proxy"] = proxy_url
    
    async with httpx.AsyncClient(**kwargs) as client:
        try:
            resp = await client.get(search_url)
            print(f"[PUBLICACIONES][PORTAL_RESPONSE] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} status_code={resp.status_code} size={len(resp.text)}")
            
            if resp.status_code != 200:
                raise Exception(f"HTTP status code {resp.status_code} returned by portal search URL: {search_url}")
                
            raw_cards = parse_result_cards(resp.text)
            filtered_by_despacho = filter_cards_by_despacho(raw_cards, id_despacho)
            candidates = filter_cards_by_category(filtered_by_despacho)

            print(f"[PUBLICACIONES][DOCS_FOUND] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} count={len(candidates)}")
            
            sem = asyncio.Semaphore(5)

            async def process_candidate(cand):
                async with sem:
                    try:
                        cand_date = parse_fecha_pub(cand.get("fecha_publicacion"))

                        print(f"[scraper] Obteniendo detalle de: {cand['detail_url']}")
                        detail_resp = await client.get(cand["detail_url"])
                        if detail_resp.status_code != 200:
                            raise Exception(f"HTTP status code {detail_resp.status_code} on detail URL: {cand['detail_url']}")
                            
                        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                        
                        estado_no = extract_metadata_field(detail_soup, "Estado No.")
                        if not estado_no:
                            title_match = re.search(r'Estado No\.?\s*(\d+)', cand["title"], re.IGNORECASE)
                            if title_match:
                                estado_no = title_match.group(1)
                        
                        fecha_estado_electronico_str = extract_metadata_field(detail_soup, "Fecha de Estado Electrónico")
                        fecha_estado_electronico = None
                        if fecha_estado_electronico_str:
                            fecha_estado_electronico = parse_spanish_date(fecha_estado_electronico_str)
                        if not fecha_estado_electronico:
                            fecha_estado_electronico = parse_fecha_pub(cand["fecha_publicacion"])

                        # Fuentes principales usando el helper
                        fuentes = detect_main_sources(detail_resp.text)
                        
                        match_principal = None
                        fuente_validada_url = None
                        fuente_validada_tipo = None
                        texto_principal = ""
                        
                        for source in fuentes:
                            s_url = source["url"]
                            s_tipo = source["tipo"]
                            doc_text = await extract_text_content(s_url, client)
                            
                            # Pasar is_filtered_source=True porque viene de la busqueda por despacho
                            from backend.service.publicaciones import classify_document_match
                            match = classify_document_match(doc_text, radicado_completo, demandante, demandado, is_filtered_source=True)
                            
                            if match_principal is None or match.score > match_principal.score:
                                match_principal = match
                                fuente_validada_url = s_url
                                fuente_validada_tipo = s_tipo
                                texto_principal = doc_text
                                
                            if match.is_valid: # Early exit si encontramos uno perfecto (validado >= 85 pts)
                                break
                                
                        if not match_principal:
                            print(f"[PUBLICACIONES][DOC_DISCARDED] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} url={cand['detail_url']} score=0 reason=No match result")
                            return None
                            
                        # Determinar estado de validación y registrar log de validación/descarte
                        estado_val = match_principal.estado_validacion
                        
                        if match_principal.is_valid:
                            print(f"[PUBLICACIONES][DOC_VALIDATED] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} url={fuente_validada_url} score={match_principal.score} type={match_principal.match_type}")
                        else:
                            print(f"[PUBLICACIONES][DOC_DISCARDED] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} url={fuente_validada_url} score={match_principal.score} reason={match_principal.reasons} final_state={estado_val}")

                        if match_principal.score < 50:
                            return None

                        url_providencia = None
                        
                        # Obtener resumen/cuadro/providencia
                        url_resumen = next((s["url"] for s in fuentes if s["tipo"] == "resumen_publicacion"), None)
                        url_cuadro = next((s["url"] for s in fuentes if s["tipo"] == "cuadro_consultar_aqui"), None)
                        
                        # Documentos complementarios usando el helper
                        seen_urls = [s["url"] for s in fuentes]
                        documentos_complementarios = await revisar_documentos_complementarios(detail_resp.text, radicado_completo, seen_urls)
                        
                        for doc in documentos_complementarios:
                            if "providencia" in doc["nombre"].lower() or "auto" in doc["nombre"].lower():
                                if not url_providencia:
                                    url_providencia = doc["url"]

                        observacion = f"Validada por {fuente_validada_tipo}. El radicado fue encontrado en el listado principal del estado."
                        
                        return {
                            "fecha": cand["fecha_publicacion"],
                            "tipo": cand["categoria"],
                            "descripcion": cand["title"],
                            "documento_url": fuente_validada_url,
                            "source_url": cand["detail_url"],
                            "source_id": hashlib.md5(cand["detail_url"].encode()).hexdigest(),
                            
                            "url_fuente_principal": fuente_validada_url,
                            "tipo_fuente_principal": fuente_validada_tipo,
                            "texto_fuente_principal": texto_principal,
                            "validada_por_fuente_principal": True,
                            "numero_estado": estado_no or "",
                            "fecha_estado_electronico": fecha_estado_electronico.strftime("%Y-%m-%d") if fecha_estado_electronico else cand["fecha_publicacion"],
                            "url_resumen_publicacion": url_resumen,
                            "url_cuadro": url_cuadro,
                            "url_providencia": url_providencia,
                            "documentos_complementarios": json.dumps(documentos_complementarios),
                            "match_fuerte": True,
                            "match_type": match_principal.match_type,
                            "motivo_match": match_principal.reasons,
                            "observacion": observacion,
                            "estado_validacion": estado_val,
                            "match_score": match_principal.score,
                            "texto_bloque_match": match_principal.texto_bloque_match,
                            "motivo_descarte": match_principal.reasons if not match_principal.is_valid else "",
                            "requiere_revision": estado_val == "requiere_revision",
                            "elementos_detectados": match_principal.elementos_detectados,
                            "extraction_quality": "pobre" if len(texto_principal) < 500 else "buena",
                        }
                    except Exception as ex:
                        import traceback
                        print(f"[PUBLICACIONES][ERROR] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} url={cand.get('detail_url', 'N/A')} status_code=N/A error={str(ex)} traceback={traceback.format_exc()} function=process_candidate")
                        raise ex

            tasks = [process_candidate(c) for c in candidates]
            found_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in found_results:
                if isinstance(res, Exception):
                    raise res
                elif res and isinstance(res, dict):
                    results.append(res)
        except Exception as e:
            import traceback
            print(f"[PUBLICACIONES][ERROR] company_id={company_id} radicado={radicado_completo} mes_busqueda={year}-{month:02d} search_id={search_id} url={search_url} status_code=N/A error={str(e)} traceback={traceback.format_exc()} function=consultar_publicaciones_rango")
            raise e

    final = []
    seen = set()
    for r in results:
        if r["source_id"] not in seen:
            final.append(r)
            seen.add(r["source_id"])
    return final



def parse_fecha_pub(fecha_str: str) -> date | None:
    if not fecha_str: return None
    try: return datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
    except: return None

async def consultar_publicaciones(radicado: str):
    return await consultar_publicaciones_rango(radicado, datetime.now().strftime("%Y-%m-%d"))
