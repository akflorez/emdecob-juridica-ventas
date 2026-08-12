import re
import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import JudicialSourceConnector
from .config import JUDICIAL_SOURCE_URLS

logger = logging.getLogger(__name__)

class SICConnector(JudicialSourceConnector):
    """
    Conector oficial para la Superintendencia de Industria y Comercio (SIC)
    Portal: https://consultatramites.sic.gov.co/consulta-externa
    API: https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados
    """
    source_name = "SIC"
    
    def __init__(self):
        self.config = JUDICIAL_SOURCE_URLS.get(self.source_name, {})
        self.base_url = self.config.get("base_url", "https://apiexternotramites.sic.gov.co/consulta-externa")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://consultatramites.sic.gov.co",
            "Referer": "https://consultatramites.sic.gov.co/"
        }

    def parse_sic_radicado(self, radicado: str) -> Optional[Dict[str, str]]:
        """
        Parsea formatos de radicado de la SIC:
        - '26-64018' -> anio='26', numero='64018'
        - '2026-64018' -> anio='26', numero='64018'
        - '25-107449' -> anio='25', numero='107449'
        - '24-455302' -> anio='24', numero='455302'
        """
        if not radicado:
            return None
            
        clean = re.sub(r'[\s\x00-\x1f\x7f-\x9f]', '', str(radicado).strip())
        
        # Formato con guión: 26-64018 o 2026-64018
        m_dash = re.match(r'^(?:20)?(\d{2})-(\d+)$', clean)
        if m_dash:
            return {"anio": m_dash.group(1), "numero": m_dash.group(2)}
            
        # Formato todo junto pero longitud corta (ej: 2664018)
        if len(clean) >= 6 and len(clean) <= 12 and clean.isdigit():
            # Si empieza con 24, 25, 26
            if clean[:2] in ["20", "21", "22", "23", "24", "25", "26", "27"]:
                return {"anio": clean[:2], "numero": clean[2:]}
                
        return None

    def supports(self, radicado: str, metadata: dict = None) -> bool:
        """
        Determina si el radicado pertenece a la SIC:
        - Si tiene formato 'AA-NNNNNN'
        - O si en metadata o juzgado viene indicado 'SIC' o 'Superintendencia'
        """
        if self.parse_sic_radicado(radicado):
            return True
            
        if metadata:
            juzgado = str(metadata.get("juzgado", "")).upper()
            if "SIC" in juzgado or "SUPERINTENDENCIA" in juzgado:
                return True
                
        return False

    def search_case(self, radicado: str, metadata: dict = None, turnstile_token: str = None) -> Dict[str, Any]:
        """
        Consulta la API oficial de la SIC para obtener datos del trámite y actuaciones.
        Requiere la Cédula/NIT en metadata (ej: metadata={'cedula': '1143957035'})
        """
        parsed = self.parse_sic_radicado(radicado)
        if not parsed:
            return {
                "status": "unsupported", 
                "message": f"El radicado '{radicado}' no tiene el formato de la SIC (ej: 26-64018)."
            }
            
        anio = parsed["anio"]
        numero = parsed["numero"]
        
        cedula = None
        if metadata:
            cedula = metadata.get("cedula") or metadata.get("cc") or metadata.get("documento")
            
        # Limpiar cédula de formato decimal (ej: '1143957035.0' -> '1143957035')
        if cedula:
            cedula = str(cedula).strip().replace(".0", "")
            cedula = re.sub(r'\D', '', cedula)
            
        endpoint = f"{self.base_url}/v1/radicados/anio/{anio}/numeros/{numero}"
        params = {
            "tipoDocumento": "CC",
            "numeroDocumento": cedula or ""
        }
        
        req_headers = dict(self.headers)
        if turnstile_token:
            req_headers["X-Turnstile-Token"] = turnstile_token
            
        try:
            r = requests.get(endpoint, params=params, headers=req_headers, timeout=12)
            
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and data.get("data"):
                    tramite_info = data["data"]
                    return {
                        "status": "success",
                        "source": self.source_name,
                        "url": f"https://consultatramites.sic.gov.co/consulta-externa?anio={anio}&numero={numero}",
                        "data": self._map_sic_data(tramite_info, radicado, anio, numero, metadata)
                    }
                else:
                    return {
                        "status": "not_found",
                        "source": self.source_name,
                        "message": data.get("message") or "No se encontraron trámites en la SIC para este radicado y cédula."
                    }
            elif r.status_code == 400:
                resp_json = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                msg = resp_json.get("message", "")
                if "verificaci" in msg.lower():
                    # Fallback controlado: si el portal exige token en tiempo real
                    # Guardamos la estructura del caso basada en la información disponible del archivo/metadata
                    return {
                        "status": "captcha_required",
                        "source": self.source_name,
                        "message": "Consulta protegida por verificación Turnstile en portal SIC.",
                        "data": self._build_offline_sic_data(radicado, anio, numero, metadata)
                    }
                return {
                    "status": "error",
                    "source": self.source_name,
                    "message": msg or f"Error 400 en consulta SIC: {r.text[:200]}"
                }
            elif r.status_code == 404:
                return {
                    "status": "not_found",
                    "source": self.source_name,
                    "message": "Trámite no encontrado en la SIC."
                }
            else:
                return {
                    "status": "error",
                    "source": self.source_name,
                    "message": f"Respuesta HTTP {r.status_code} desde el servidor de la SIC."
                }
        except Exception as e:
            logger.error(f"[SICConnector] Error consultando SIC {radicado}: {e}")
            return {
                "status": "error",
                "source": self.source_name,
                "message": f"Error de conexión con portal SIC: {str(e)}",
                "data": self._build_offline_sic_data(radicado, anio, numero, metadata)
            }

    def _build_offline_sic_data(self, radicado: str, anio: str, numero: str, metadata: dict = None) -> Dict[str, Any]:
        """
        Construye la estructura de datos para un caso SIC asegurando que no se pierdan demandante/demandado del Excel
        """
        meta = metadata or {}
        return {
            "radicado": radicado,
            "despacho": "Superintendencia de Industria y Comercio - SIC",
            "juzgado": "SIC",
            "tipo_proceso": "Demanda Protección al Consumidor Jurisdiccional",
            "demandante": meta.get("demandante"),
            "demandado": meta.get("demandado") or meta.get("demandando"),
            "estado": meta.get("estado") or "En trámite",
            "fuente": "SIC",
            "es_sic": True,
            "actuaciones": []
        }

    def _map_sic_data(self, tramite_info: Any, radicado: str, anio: str, numero: str, metadata: dict = None) -> Dict[str, Any]:
        """
        Mapea el objeto retornado por la API de la SIC a la estructura estándar de JURICOB
        """
        meta = metadata or {}
        
        actuaciones = []
        # Si la respuesta contiene lista de actuaciones/eventos en content o actuaciones
        items = tramite_info if isinstance(tramite_info, list) else (tramite_info.get("content", []) or tramite_info.get("actuaciones", []))
        
        for item in items:
            raw_fecha = str(item.get("fecha") or item.get("fechaRadicado") or item.get("fechaRadicacion") or "").strip()
            fecha_str = ""
            if raw_fecha:
                if "/" in raw_fecha:
                    parts = raw_fecha.split()[0].split("/")
                    if len(parts) == 3:
                        if len(parts[2]) == 4:
                            fecha_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                        else:
                            fecha_str = f"20{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                elif "-" in raw_fecha:
                    fecha_str = raw_fecha[:10]
            if not fecha_str:
                fecha_str = datetime.utcnow().strftime("%Y-%m-%d")

            act_title = (item.get("actuacion") or item.get("actuacionRadicado") or item.get("evento") or item.get("eventoRadicado") or "Actuación SIC").strip()
            tramite = (item.get("tramite") or item.get("tramiteRadicado") or "DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL").strip()
            solicitante = (item.get("solicitante") or item.get("solicitanteDestinatario") or item.get("destinatario") or "").strip()
            tipo = (item.get("tipo") or item.get("tipoRadicado") or "").strip()
            
            anotacion_parts = [f"Trámite: {tramite}"]
            if tipo: anotacion_parts.append(f"Tipo: {tipo}")
            if solicitante: anotacion_parts.append(f"Sujeto: {solicitante}")
            
            actuaciones.append({
                "fecha": fecha_str,
                "actuacion": act_title,
                "anotacion": " | ".join(anotacion_parts),
                "fecha_registro": raw_fecha or fecha_str,
                "url_documento": None
            })
            
        # Ordenar actuaciones de la más reciente a la más antigua
        actuaciones.sort(key=lambda x: x.get("fecha", ""), reverse=True)
        
        # Determinar última actuación
        ultima_act = actuaciones[0].get("fecha") if actuaciones else None
            
        return {
            "radicado": radicado,
            "despacho": "Superintendencia de Industria y Comercio - SIC",
            "juzgado": "SIC",
            "tipo_proceso": "Demanda Protección al Consumidor Jurisdiccional",
            "demandante": meta.get("demandante") or (actuaciones[0].get("anotacion") if actuaciones else None),
            "demandado": meta.get("demandado") or meta.get("demandando"),
            "estado": meta.get("estado") or "En trámite",
            "ultima_actuacion": ultima_act,
            "fuente": "SIC",
            "es_sic": True,
            "actuaciones": actuaciones
        }
