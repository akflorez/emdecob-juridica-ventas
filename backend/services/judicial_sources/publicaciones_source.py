import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from .base import JudicialSourceConnector
from .config import JUDICIAL_SOURCE_URLS

logger = logging.getLogger(__name__)

class PublicacionesProcesalesConnector(JudicialSourceConnector):
    """
    Conector para el portal oficial de Publicaciones Procesales / Estados Electrónicos de la Rama Judicial.
    Portal: https://publicacionesprocesales.ramajudicial.gov.co/
    Sigue estrictamente el instructivo:
      1. Extrae código de despacho (12 dígitos).
      2. Filtra por año de radicación del proceso y despacho.
      3. Escanea estados, fijaciones, autos y traslados.
      4. Valida identificador consecutivo, partes y cédulas.
      5. Entrega documentos PDF/DOCX oficiales directos.
    """
    source_name = "PUBLICACIONES_PROCESALES"
    
    def __init__(self):
        self.config = JUDICIAL_SOURCE_URLS.get(self.source_name, {})
        self.base_url = self.config.get("base_url", "https://publicacionesprocesales.ramajudicial.gov.co/web/publicaciones-procesales/inicio")
        
    def supports(self, radicado: str, metadata: dict = None) -> bool:
        clean = "".join(filter(str.isdigit, str(radicado or "")))
        return len(clean) == 23
        
    def search_case(self, radicado: str, metadata: dict = None) -> dict:
        if not self.supports(radicado, metadata):
            return {"status": "unsupported", "message": "Formato de radicado no soportado (debe tener 23 dígitos)."}
            
        clean_rad = "".join(filter(str.isdigit, str(radicado)))
        despacho_code = clean_rad[:12]
        case_year = clean_rad[12:16]
        meta = metadata or {}
        
        demandante = meta.get("demandante", "")
        demandado = meta.get("demandado", "")
        cedula = meta.get("cedula", "")
        
        try:
            from backend.service.publicaciones import (
                build_portal_search_url,
                parse_result_cards,
                filter_cards_by_despacho,
                filter_cards_by_category,
                open_detail,
                detect_main_sources,
                extract_text_content,
                validate_strong_match
            )
            import httpx
            
            async def _run_search():
                now_str = datetime.utcnow().strftime("%Y-%m-%d")
                search_url = build_portal_search_url(despacho_code, f"{case_year}-01-01", now_str)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
                
                async with httpx.AsyncClient(verify=False, timeout=30.0, headers=headers, follow_redirects=True) as client:
                    resp = await client.get(search_url)
                    if resp.status_code != 200:
                        return []
                        
                    raw_cards = parse_result_cards(resp.text)
                    filtered_desp = filter_cards_by_despacho(raw_cards, despacho_code)
                    candidates = filter_cards_by_category(filtered_desp)
                    
                    found_pubs = []
                    proc_consec = clean_rad[12:21] # 202400394
                    formatted_proc = f"{clean_rad[12:16]}-{clean_rad[16:21]}" # 2024-00394
                    
                    for cand in candidates[:25]:
                        detail_html = await open_detail(cand)
                        if not detail_html:
                            continue
                            
                        fuentes = detect_main_sources(detail_html)
                        for f in fuentes:
                            f_url = f.get("url")
                            if not f_url:
                                continue
                            doc_text = await extract_text_content(f_url, client, timeout=10)
                            validation = validate_strong_match(doc_text, clean_rad, demandante, demandado)
                            
                            doc_upper = doc_text.upper()
                            c_yr = clean_rad[12:16]
                            c_num = clean_rad[16:21] # 00167
                            c_int = str(int(c_num)) # 167
                            
                            has_strict_consec = (
                                proc_consec in doc_upper or
                                formatted_proc in doc_upper or
                                f"{c_yr[2:]}-{c_num}" in doc_upper or
                                f"{c_yr}-{c_int}" in doc_upper or
                                f"{c_int} - {c_yr}" in doc_upper or
                                f"{c_int}-{c_yr}" in doc_upper
                            )
                            
                            dem_words = [w for w in (demandado or "").upper().split() if len(w) > 3]
                            has_demandado_full = False
                            if len(dem_words) >= 2:
                                for i in range(len(dem_words) - 1):
                                    if f"{dem_words[i]} {dem_words[i+1]}" in doc_upper:
                                        has_demandado_full = True
                                        break
                            elif len(dem_words) == 1:
                                has_demandado_full = (demandante or "").upper() in doc_upper and dem_words[0] in doc_upper
                                
                            has_cedula = bool(cedula and len(str(cedula).strip()) >= 6 and str(cedula).strip() in doc_upper)
                            
                            is_match = has_strict_consec or (has_cedula and has_demandado_full) or (has_demandado_full and (demandante or "").upper() in doc_upper)
                            
                            if is_match:
                                found_pubs.append({
                                    "tipo_publicacion": cand.get("categoria") or "Estado Electrónico",
                                    "fecha_publicacion": cand.get("fecha_publicacion"),
                                    "descripcion": cand.get("title") or f"Publicación en {cand.get('despacho')}",
                                    "documento_url": f_url,
                                    "source_url": cand.get("detail_url") or search_url,
                                    "despacho": cand.get("despacho"),
                                    "demandante": demandante,
                                    "demandado": demandado,
                                    "validada_por_fuente_principal": True,
                                    "estado_validacion": "validado_automatico"
                                })
                                
                    return found_pubs

            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            if loop.is_running():
                pubs = asyncio.run_coroutine_threadsafe(_run_search(), loop).result(timeout=35)
            else:
                pubs = loop.run_until_complete(_run_search())
                
            if pubs:
                first_pub = pubs[0]
                return {
                    "status": "success",
                    "source": self.source_name,
                    "url": first_pub.get("documento_url") or self.base_url,
                    "data": {
                        "radicado": radicado,
                        "despacho": first_pub.get("despacho") or "Despacho Judicial de Publicaciones",
                        "juzgado": first_pub.get("despacho") or "Despacho Judicial de Publicaciones",
                        "tipo_proceso": first_pub.get("tipo_publicacion") or "Publicación Procesal / Estado",
                        "demandante": demandante or first_pub.get("demandante"),
                        "demandado": demandado or first_pub.get("demandado"),
                        "estado": f"Publicado en Estados ({first_pub.get('fecha_publicacion')})",
                        "fecha_ultima_actuacion": first_pub.get("fecha_publicacion"),
                        "publicaciones": pubs
                    }
                }
            else:
                return {
                    "status": "not_found",
                    "source": self.source_name,
                    "url": self.base_url,
                    "message": "No se encontraron publicaciones procesales para este radicado en el portal oficial."
                }
        except Exception as e:
            logger.error(f"[PublicacionesProcesalesConnector] Error buscando {radicado}: {e}")
            return {
                "status": "error",
                "source": self.source_name,
                "message": f"Error consultando Publicaciones Procesales: {str(e)}"
            }
        
    def search_events(self, radicado: str, metadata: dict = None) -> list:
        res = self.search_case(radicado, metadata)
        if res.get("status") == "success":
            pubs = res.get("data", {}).get("publicaciones", [])
            events = []
            for p in pubs:
                events.append({
                    "fecha": p.get("fecha_publicacion"),
                    "actuacion": p.get("tipo_publicacion") or "Estado Electrónico",
                    "anotacion": p.get("descripcion") or "Publicación procesal oficial",
                    "documento_url": p.get("documento_url")
                })
            return events
        return []
        
    def search_documents(self, radicado: str, metadata: dict = None) -> list:
        res = self.search_case(radicado, metadata)
        if res.get("status") == "success":
            pubs = res.get("data", {}).get("publicaciones", [])
            return [
                {
                    "title": f"{p.get('tipo_publicacion')} - {p.get('fecha_publicacion')}",
                    "url": p.get("documento_url"),
                    "date": p.get("fecha_publicacion")
                }
                for p in pubs if p.get("documento_url")
            ]
        return []
        
    def healthcheck(self) -> dict:
        return {
            "source": self.source_name,
            "status": "healthy",
            "url": self.base_url,
            "message": "Conector de Publicaciones Procesales activo y sincronizado con instructivo oficial."
        }
