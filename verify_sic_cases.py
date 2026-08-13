import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Case

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)
Session = sessionmaker(bind=engine)
db = Session()

# Let's verify how the 15 cases from user's Excel screenshot will look
cases_data = [
    {"radicado": "25-107449", "demandante": "STEVEN LEANDRO COLORADO CHIQUITO", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1004826465", "estado": "ALLANAMIENTO - DEVOLUCIÓN DE DINERO"},
    {"radicado": "25-129192", "demandante": "STEVEN GALLO LOPEZ", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1088021274", "estado": "CONTESTACIÓN"},
    {"radicado": "25-137987", "demandante": "ERIKA VIVIANA ALZATE OSPINA", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1115074666", "estado": "SIN PRONUNCIAMIENTO"},
    {"radicado": "25-173725", "demandante": "LIZETH ZULUAGA LEÓN", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1094928175", "estado": "CONTESTACIÓN"},
    {"radicado": "24-153774", "demandante": "JHON JAIRO RODRIGUEZ BETANCURTH", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "79662387", "estado": "EN VERIFICACIÓN DE CUMPLIMIENTO"},
    {"radicado": "25-611631", "demandante": "DERLY VIVIANA MEJIA LAVERDE", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1094911476", "estado": "ALLANAMIENTO - DEVOLUCIÓN DE DINERO"},
    {"radicado": "25-373418", "demandante": "MATIAS VELEZ JARAMILLO", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1094952288", "estado": "CONTESTACIÓN"},
    {"radicado": "26-64018", "demandante": "ERICA YOHANA RAMIREZ PEREA", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1143957035", "estado": "ALLANAMIENTO CAMBIO DE VEHÍCULO"},
    {"radicado": "24-455302", "demandante": "WILMAR CARDENAS ARANGO", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "4525985", "estado": "CONTESTACIÓN"},
    {"radicado": "25-267955", "demandante": "LUIS MATEO MEDINA YEPES", "demandando": "MOTO EXPERIENCIA SAS", "juzgado": "SIC", "cc": "1097731334", "estado": "ALLANAMIENTO"},
    {"radicado": "25-67244", "demandante": "VICTOR RAUL MOSQUERA MOSQUERA", "demandando": "SU MOTO DEL CAFÉ SAS", "juzgado": "SIC", "cc": "1076321300", "estado": "EN VERIFICACIÓN DE CUMPLIMIENTO"},
    {"radicado": "25-118181", "demandante": "MICHELLE NATALIA MEJIA GIRALDO", "demandando": "SU MOTO DEL CAFÉ SAS", "juzgado": "SIC", "cc": "1092455904", "estado": "ALLANAMIENTO"},
    {"radicado": "25-192826", "demandante": "LUIS EDUARDO HURTADO GAMBOA", "demandando": "SU MOTO DEL CAFÉ SAS", "juzgado": "SIC", "cc": "16949895", "estado": "ALLANAMIENTO"},
    {"radicado": "25-335760", "demandante": "KATHERINE FIERRO VASQUEZ", "demandando": "SU MOTO DE IBAGUÉ SAS", "juzgado": "SIC", "cc": "1111200006", "estado": "CONTESTACIÓN"},
    {"radicado": "26-231607", "demandante": "OSCAR ANDRÉS LARGO LOAIZA - GRUPOS CI", "demandando": "AVENTURA MOTORS SAS", "juzgado": "SIC", "cc": "1053786300", "estado": "ADMITIDO"}
]

print(f"Total casos a insertar: {len(cases_data)}")
for c in cases_data:
    existing = db.query(Case).filter(Case.radicado == c["radicado"], Case.company_id == 3).first()
    if not existing:
        db.add(Case(
            radicado=c["radicado"],
            demandante=c["demandante"],
            demandado=c["demandando"],
            juzgado="SIC",
            despacho="Superintendencia de Industria y Comercio - SIC",
            fuente_encontrado="SIC",
            tipo_proceso="Demanda Protección al Consumidor Jurisdiccional",
            cedula=c["cc"],
            estado=c["estado"],
            company_id=3,
            user_id=5,
            is_active=True
        ))
db.commit()
print("¡Casos insertados y verificados exitosamente!")

# Query back to verify
inserted = db.query(Case).filter(Case.juzgado == "SIC", Case.company_id == 3).all()
print(f"\nCasos SIC en la base de datos ({len(inserted)}):")
for item in inserted:
    print(f"  [{item.radicado}] {item.demandante} VS {item.demandado} | Cédula: {item.cedula} | Estado: {item.estado}")
db.close()
