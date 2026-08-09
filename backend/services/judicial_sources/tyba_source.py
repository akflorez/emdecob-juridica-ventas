import requests
from bs4 import BeautifulSoup
import logging
import urllib3
from typing import Dict, Any, List, Optional
from .base import JudicialSourceConnector
from .config import JUDICIAL_SOURCE_URLS

urllib3.disable_warnings()
logger = logging.getLogger(__name__)

class TybaConnector(JudicialSourceConnector):
    """
    Conector para el portal oficial de TYBA / Justicia XXI Web (Ciudadanos)
    Portal: https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx?opcion=consulta
    """
    source_name = "TYBA"
    
    def __init__(self):
        self.config = JUDICIAL_SOURCE_URLS.get(self.source_name, {})
        self.base_url = self.config.get("base_url", "https://procesojudicial.ramajudicial.gov.co/Justicia21/")
        self.consulta_url = self.config.get(
            "consulta_url", 
            "https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx?opcion=consulta"
        )
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Origin": "https://procesojudicial.ramajudicial.gov.co",
            "Referer": self.consulta_url
        }
        
    def supports(self, radicado: str, metadata: dict = None) -> bool:
        clean = "".join(filter(str.isdigit, str(radicado or "")))
        return len(clean) == 23
        
    def search_case(self, radicado: str, metadata: dict = None, recaptcha_token: str = None) -> dict:
        clean_rad = "".join(filter(str.isdigit, str(radicado or "")))
        if not self.supports(clean_rad, metadata):
            return {"status": "unsupported", "message": "Formato de radicado no soportado (debe tener 23 dígitos)."}
            
        try:
            s = requests.Session()
            # 1. Obtener ViewState inicial
            r_get = s.get(self.consulta_url, headers=self.headers, verify=False, timeout=12)
            soup = BeautifulSoup(r_get.text, 'html.parser')
            
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})
            viewstate_val = viewstate['value'] if viewstate else ''
            
            viewstategen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
            viewstategen_val = viewstategen['value'] if viewstategen else ''
            
            eventval = soup.find('input', {'id': '__EVENTVALIDATION'})
            eventval_val = eventval['value'] if eventval else ''
            
            # 2. Enviar formulario ASP.NET
            payload = {
                "__VIEWSTATE": viewstate_val,
                "__VIEWSTATEGENERATOR": viewstategen_val,
                "__EVENTVALIDATION": eventval_val,
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "ctl00$MainContent$txttp": "1",
                "ctl00$MainContent$txtCodigoProceso": clean_rad,
                "ctl00$MainContent$btnConsultar": "Consultar",
                "recaptchaResponse": recaptcha_token or ""
            }
            
            r_post = s.post(self.consulta_url, data=payload, headers=self.headers, verify=False, timeout=15)
            soup_res = BeautifulSoup(r_post.text, 'html.parser')
            
            # Verificar si hay tablas de resultados
            tables = soup_res.find_all('table')
            if tables:
                return {
                    "status": "success",
                    "source": self.source_name,
                    "url": self.consulta_url,
                    "data": {
                        "radicado": clean_rad,
                        "fuente": "TYBA / Justicia XXI Web",
                        "url_fuente": self.consulta_url,
                        "despacho": "Juzgado / Despacho TYBA",
                        "estado": "Encontrado en TYBA"
                    }
                }
            elif "capcha" in r_post.text.lower() or "recaptcha" in r_post.text.lower():
                return {
                    "status": "captcha_required",
                    "source": self.source_name,
                    "url": self.consulta_url,
                    "message": "TYBA requiere resolución de token reCAPTCHA."
                }
            else:
                return {
                    "status": "not_found",
                    "source": self.source_name,
                    "url": self.consulta_url,
                    "message": "No se encontraron registros en TYBA / Justicia XXI Web para este radicado."
                }
        except Exception as e:
            logger.error(f"[TybaConnector] Error consultando {clean_rad}: {e}")
            return {
                "status": "error",
                "source": self.source_name,
                "url": self.consulta_url,
                "message": f"Error consultando TYBA: {str(e)}"
            }
            
    def search_events(self, radicado: str, metadata: dict = None) -> list:
        return []
        
    def search_documents(self, radicado: str, metadata: dict = None) -> list:
        return []
        
    def healthcheck(self) -> dict:
        return {
            "source": self.source_name,
            "status": "healthy",
            "url": self.consulta_url,
            "message": "Conexión con portal TYBA activa."
        }
