from backend.services.judicial_sources.sic_source import SICConnector

connector = SICConnector()

cases_test = [
    {"radicado": "25-107449", "demandante": "STEVEN LEANDRO COLORADO CHIQUITO", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1004826465", "estado": "ALLANAMIENTO - DEVOLUCIÓN DE DINERO"},
    {"radicado": "25-129192", "demandante": "STEVEN GALLO LOPEZ", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1088021274", "estado": "CONTESTACIÓN"},
    {"radicado": "26-64018", "demandante": "ERICA YOHANA RAMIREZ PEREA", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1143957035", "estado": "ALLANAMIENTO CAMBIO DE VEHÍCULO"},
    {"radicado": "24-455302", "demandante": "WILMAR CARDENAS ARANGO", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "4525985", "estado": "CONTESTACIÓN"},
    {"radicado": "26-231607", "demandante": "OSCAR ANDRÉS LARGO LOAIZA", "demandando": "AVENTURA MOTORS SAS", "juzgado": "SIC", "cc": "1053786300", "estado": "ADMITIDO"}
]

print("=== TESTING SIC CONNECTOR ===")
for c in cases_test:
    parsed = connector.parse_sic_radicado(c["radicado"])
    supported = connector.supports(c["radicado"], metadata=c)
    print(f"Radicado: {c['radicado']} | Parsed: {parsed} | Supported: {supported}")
    
    # Test search
    res = connector.search_case(c["radicado"], metadata=c)
    print(f"  Result status: {res.get('status')} | Source: {res.get('source')}")
    data = res.get("data", {})
    print(f"  Data: Despacho={data.get('despacho')} | Demandante={data.get('demandante')} | Demandado={data.get('demandado')} | Estado={data.get('estado')}")
    print()
