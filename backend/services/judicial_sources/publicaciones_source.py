import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import JudicialSourceConnector
from .config import JUDICIAL_SOURCE_URLS

logger = logging.getLogger(__name__)

class PublicacionesProcesalesConnector(JudicialSourceConnector):
    """
    Conector para el portal oficial de Publicaciones Procesales / Estados Electrónicos
    Portal: https://publicacionesprocesales.ramajudicial.gov.co/
    """
    source_name = "PUBLICACIONES_PROCESALES"
    
    def __init__(self):
        self.config = JUDICIAL_SOURCE_URLS.get(self.source_name, {})
        self.base_url = self.config.get("base_url", "https://publicacionesprocesales.ramajudicial.gov.co/")
        
    def supports(self, radicado: str, metadata: dict = None) -> bool:
        # Standard Colombian judicial code format (23 digits)
        clean = "".join(filter(str.isdigit, str(radicado or "")))
        return len(clean) == 23
        
    def search_case(self, radicado: str, metadata: dict = None) -> dict:
        if not self.supports(radicado, metadata):
            return {"status": "unsupported", "message": "Formato de radicado no soportado (debe tener 23 dígitos)."}
            
        try:
            from backend.service.publicaciones import consultar_publicaciones, parse_radicado
            
            # Ejecutar la búsqueda en el portal de Publicaciones Procesales
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            if loop.is_running():
                # Si estamos dentro de un async loop, usamos un runner o task
                future = asyncio.ensure_future(consultar_publicaciones(radicado))
                # Esperar resultado
                pubs = asyncio.run_coroutine_threadsafe(consultar_publicaciones(radicado), loop).result(timeout=25)
            else:
                pubs = loop.run_until_complete(consultar_publicaciones(radicado))
                
            if pubs:
                first_pub = pubs[0]
                rad_info = parse_radicado(radicado)
                
                return {
                    "status": "success",
                    "source": self.source_name,
                    "url": first_pub.get("documento_url") or self.base_url,
                    "data": {
                        "radicado": radicado,
                        "despacho": first_pub.get("despacho") or "Despacho Judicial de Publicaciones",
                        "juzgado": first_pub.get("despacho") or "Despacho Judicial de Publicaciones",
                        "tipo_proceso": first_pub.get("tipo_publicacion") or "Publicación Procesal / Estado",
                        "demandante": first_pub.get("demandante"),
                        "demandado": first_pub.get("demandado"),
                        "estado": "Publicado en Estados Electrónicos",
                        "fecha_ultima_actuacion": first_pub.get("fecha_publicacion"),
                        "publicaciones": pubs
                    }
                }
            else:
                return {
                    "status": "not_found",
                    "source": self.source_name,
                    "url": self.base_url,
                    "message": "No se encontraron publicaciones procesales para este radicado."
                }
        except Exception as e:
            logger.error(f"[PublicacionesProcesalesConnector] Error buscando {radicado}: {e}")
            return {
                "status": "error",
                "source": self.source_name,
                "message": f"Error consultando Publicaciones Procesales: {str(e)}"
            }
        
    def search_events(self, radicado: str, metadata: dict = None) -> list:
        return []
        
    def search_documents(self, radicado: str, metadata: dict = None) -> list:
        return []
        
    def healthcheck(self) -> dict:
        return {
            "source": self.source_name,
            "status": "healthy",
            "url": self.base_url,
            "message": "Conexión con el micrositio activa."
        }
