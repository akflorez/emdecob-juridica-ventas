import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import sys

logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.judicial_sources.sic_source import SICConnector
from backend.services.sic_turnstile_solver import fetch_sic_actuations_live, sync_sic_case_to_db

def run_sic_background_sweep():
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Consultar todos los casos pertenecientes a la SIC
        cases = session.execute(text("""
            SELECT id, radicado, cedula, demandante 
            FROM cases 
            WHERE (juzgado ILIKE '%SIC%' OR fuente_encontrado ILIKE '%SIC%' OR radicado ~ '^(24|25|26)-')
              AND is_active = true
            ORDER BY id ASC
        """)).fetchall()

        logger.info(f"🚀 Iniciando barrido automático desatendido para {len(cases)} casos de la SIC...")

        success_count = 0
        for c in cases:
            cid = c.id
            rad = c.radicado
            ced = c.cedula or ""

            parts = rad.split("-") if "-" in rad else ["25", rad]
            anio = parts[0]
            numero = parts[1] if len(parts) > 1 else rad

            logger.info(f"🔄 Procesando caso SIC ID {cid} ({rad})...")

            items = fetch_sic_actuations_live(anio=anio, numero=numero, cedula=ced)
            if items:
                count = sync_sic_case_to_db(session, cid, items)
                logger.info(f"✅ Caso ID {cid} ({rad}) actualizado automáticamente con {count} actuaciones!")
                success_count += 1
            else:
                logger.warning(f"⚠️ Barrido SIC pendiente de token o respuesta para caso ID {cid} ({rad})")

            time.sleep(2)

        logger.info(f"✨ Barrido desatendido de la SIC completado. {success_count}/{len(cases)} casos actualizados.")
    except Exception as e:
        logger.error(f"Error en barrido automático SIC: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_sic_background_sweep()
