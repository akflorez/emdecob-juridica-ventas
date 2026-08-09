import os

# Feature flags for multisource checks (Fase 1 compliance defaults)
MULTISOURCE_ENABLED = os.getenv("MULTISOURCE_ENABLED", "true").lower() == "true"
MULTISOURCE_DRY_RUN = os.getenv("MULTISOURCE_DRY_RUN", "true").lower() == "true"
MULTISOURCE_TIMEOUT_SECONDS = int(os.getenv("MULTISOURCE_TIMEOUT_SECONDS", "30"))
MULTISOURCE_MAX_RETRIES = int(os.getenv("MULTISOURCE_MAX_RETRIES", "2"))
MULTISOURCE_CONCURRENCY = int(os.getenv("MULTISOURCE_CONCURRENCY", "1"))
MULTISOURCE_SLEEP_MS = int(os.getenv("MULTISOURCE_SLEEP_MS", "1000"))

# Official source mappings
JUDICIAL_SOURCE_URLS = {
    "PUBLICACIONES_PROCESALES": {
        "name": "Publicaciones Procesales / Estados Electrónicos",
        "base_url": "https://publicacionesprocesales.ramajudicial.gov.co/",
        "historical_url": "https://publicacionesprocesales.ramajudicial.gov.co/web/publicaciones-procesales/consulta-historica"
    },
    "SIUGJ": {
        "name": "SIUGJ",
        "base_url": "https://siugj.ramajudicial.gov.co/principalPortal/index.php",
        "consulta_proceso_url": "https://siugj.ramajudicial.gov.co/principalPortal/consultarProceso.php",
        "publicaciones_url": "https://siugj.ramajudicial.gov.co/principalPortal/publicaciones.php",
        "consultas_externas_url": "https://siugj-sgde.ramajudicial.gov.co/consultas-externas/"
    },
    "TYBA": {
        "name": "TYBA / Justicia XXI Web",
        "base_url": "https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx?opcion=consulta",
        "consulta_url": "https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx?opcion=consulta"
    },
    "SAMAI": {
        "name": "SAMAI",
        "base_url": "https://samai.consejodeestado.gov.co/",
        "consulta_consejo_estado_url": "https://www.consejodeestado.gov.co/consulta/index.htm"
    },
    "SIC": {
        "name": "Superintendencia de Industria y Comercio - SIC",
        "base_url": "https://apiexternotramites.sic.gov.co/consulta-externa",
        "portal_url": "https://consultatramites.sic.gov.co/consulta-externa"
    }
}
