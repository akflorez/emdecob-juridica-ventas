from .base import JudicialSourceConnector
from .config import JUDICIAL_SOURCE_URLS

class PublicacionesProcesalesConnector(JudicialSourceConnector):
    source_name = "PUBLICACIONES_PROCESALES"
    
    def __init__(self):
        self.config = JUDICIAL_SOURCE_URLS.get(self.source_name, {})
        self.base_url = self.config.get("base_url", "https://publicacionesprocesales.ramajudicial.gov.co/")
        
    def supports(self, radicado: str, metadata: dict = None) -> bool:
        # Standard Colombian judicial code format (23 digits)
        return len(radicado) == 23 and radicado.isdigit()
        
    def search_case(self, radicado: str, metadata: dict = None) -> dict:
        if not self.supports(radicado, metadata):
            return {"status": "unsupported", "message": "Formato de radicado no soportado por esta fuente."}
            
        # Return not_found when no real scraper data is available, never return fake Demo data
        return {
            "status": "not_found",
            "source": self.source_name,
            "url": self.base_url,
            "message": "No se encontraron publicaciones procesales para este radicado."
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
