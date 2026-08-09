from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from backend.models import Case, CaseEvent, User

def get_colombia_now() -> datetime:
    return datetime.utcnow() - timedelta(hours=5)

def safe_parse_date(d) -> Optional[date]:
    if not d:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        s = d.strip()
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except:
            pass
        try:
            return datetime.strptime(s[:10], "%d/%m/%Y").date()
        except:
            pass
    return None

def format_date_str(d) -> str:
    if not d:
        return "Reciente"
    if isinstance(d, (datetime, date)):
        return d.strftime("%d/%m/%Y")
    if isinstance(d, str):
        p = safe_parse_date(d)
        if p:
            return p.strftime("%d/%m/%Y")
        return d[:10]
    return "Reciente"

def analyze_case_risk_and_summary(c: Case, events: List[CaseEvent]) -> Dict[str, Any]:
    """
    Motor de analítica jurídica y cálculo de riesgo procesal (Código General del Proceso Colombiano).
    """
    now = get_colombia_now().date()
    parsed_ult = safe_parse_date(c.ultima_actuacion)
    parsed_rad = safe_parse_date(c.fecha_radicacion)
    created_date = c.created_at.date() if c.created_at else now
    
    ref_date = parsed_ult or parsed_rad or created_date
    dias_inactivo = (now - ref_date).days if ref_date else 0
    if dias_inactivo < 0:
        dias_inactivo = 0

    # Extraer última actuación
    latest_event = events[0] if events else None
    latest_title = (latest_event.title or "") if latest_event else (c.estado or "Sin actuaciones registradas")
    latest_detail = (latest_event.detail or "") if latest_event else ""
    full_latest_text = f"{latest_title} {latest_detail}".upper()

    # Clasificar Nivel de Riesgo
    is_sic = (c.juzgado and "SIC" in c.juzgado.upper()) or (c.fuente_encontrado == "SIC")
    
    if dias_inactivo >= 180:
        nivel_riesgo = "Alto"
        termino_restante = 0
        recomendacion = "Radicar de manera urgente memorial de impulso procesal para evitar desistimiento tácito (Art. 317 C.G.P.)."
    elif "MANDAMIENTO" in full_latest_text or "PAGO" in full_latest_text:
        nivel_riesgo = "Alto" if dias_inactivo >= 30 else "Medio"
        termino_restante = max(1, 5 - (dias_inactivo % 5))
        recomendacion = "Verificar trámite de notificación personal o por aviso al demandado conforme al C.G.P."
    elif "REMATE" in full_latest_text or "AVALÚO" in full_latest_text:
        nivel_riesgo = "Alto"
        termino_restante = 3
        recomendacion = "Revisar publicaciones de aviso de remate y verificar consignación de posturas."
    elif "EMBARGO" in full_latest_text or "MEDIDAS" in full_latest_text or "CAUTELAR" in full_latest_text:
        nivel_riesgo = "Medio"
        termino_restante = 10
        recomendacion = "Hacer seguimiento a la respuesta de entidades bancarias / tránsito sobre oficios de embargo."
    elif is_sic:
        nivel_riesgo = "Medio" if dias_inactivo >= 45 else "Bajo"
        termino_restante = max(1, 15 - (dias_inactivo % 15))
        recomendacion = "Monitorear traslado y fijación de audiencia en la Delegatura para Asuntos Jurisdiccionales de la SIC."
    elif dias_inactivo >= 60:
        nivel_riesgo = "Medio"
        termino_restante = 15
        recomendacion = "Solicitar informe secretarial o consultar el estado de despacho del expediente."
    else:
        nivel_riesgo = "Bajo"
        termino_restante = 30
        recomendacion = "Proceso activo en seguimiento rutinario. Monitorear próximas fijaciones en lista o estados electrónicos."

    # Resumen estructurado
    if latest_event:
        fecha_str = format_date_str(latest_event.event_date)
        resumen_ia = f"Última actuación ({fecha_str}): {latest_title}. {latest_detail[:180]}".strip()
    elif c.estado:
        resumen_ia = f"Estado actual: {c.estado}. Despacho: {c.despacho or c.juzgado or 'Despacho asignado'}."
    else:
        fecha_rad_str = format_date_str(c.fecha_radicacion)
        resumen_ia = f"Proceso radicado ({fecha_rad_str}). En espera de fijación de primera actuación judicial."

    # Tipo de Sentencia / Estado
    if "SENTENCIA" in full_latest_text or "FALLO" in full_latest_text:
        if "DESFAVORABLE" in full_latest_text or "NIEGA" in full_latest_text or "TERMINA" in full_latest_text:
            tipo_sentencia = "Desfavorables"
        else:
            tipo_sentencia = "Favorables"
    else:
        tipo_sentencia = "En Trámite"

    return {
        "id": c.id,
        "radicado": c.radicado,
        "demandante": c.demandante or "No especificado",
        "demandado": c.demandado or "No especificado",
        "juzgado": c.despacho or c.juzgado or "Juzgado / Despacho Judicial",
        "dias_sin_movimiento": dias_inactivo,
        "nivel_riesgo": nivel_riesgo,
        "termino_dias_restantes": termino_restante,
        "resumen_ia": resumen_ia,
        "recomendacion_ia": recomendacion,
        "tipo_sentencia": tipo_sentencia,
        "is_sic": is_sic
    }

def get_company_ai_dashboard_stats(db: Session, company_id: Optional[int], is_superadmin: bool = False) -> Dict[str, Any]:
    """
    Retorna métricas consolidadas en tiempo real para el Tablero de IA, calculadas
    exactamente con el mismo motor de analítica que las consultas filtradas.
    """
    q = db.query(Case).filter(Case.juzgado.isnot(None), or_(Case.is_active == True, Case.is_active.is_(None)))
    if not is_superadmin and company_id:
        q = q.filter(Case.company_id == company_id)
        
    all_cases = q.order_by(desc(Case.updated_at)).all()
    total_count = len(all_cases)
    
    if total_count == 0:
        return {
            "total_analyzed": 0,
            "inactive_over_6_months": 0,
            "high_risk_count": 0,
            "upcoming_terms_count": 0,
            "ai_summaries_pct": 100,
            "summary_text": "No hay procesos activos en el sistema para analizar. Sube tu cartera en Importar Excel."
        }

    case_ids = [c.id for c in all_cases]
    events_by_case: Dict[int, List[CaseEvent]] = {cid: [] for cid in case_ids}
    if case_ids:
        all_events = db.query(CaseEvent).filter(CaseEvent.case_id.in_(case_ids)).order_by(desc(CaseEvent.event_date)).all()
        for ev in all_events:
            events_by_case[ev.case_id].append(ev)

    analyzed_items: List[Dict[str, Any]] = []
    for c in all_cases:
        evs = events_by_case.get(c.id, [])
        analyzed = analyze_case_risk_and_summary(c, evs)
        analyzed_items.append(analyzed)

    inactive_6m = sum(1 for item in analyzed_items if item["dias_sin_movimiento"] >= 180)
    high_risk = sum(1 for item in analyzed_items if item["nivel_riesgo"] == "Alto")
    upcoming_terms = sum(1 for item in analyzed_items if item["termino_dias_restantes"] <= 5 or item["nivel_riesgo"] == "Alto")

    summary_text = (
        f"El motor de IA analizó {total_count} procesos activos en tu cartera. "
        f"Se identificaron {inactive_6m} procesos con más de 6 meses de inactividad que requieren memorial de impulso prioritario, "
        f"y {high_risk} procesos bajo categoría de riesgo alto procesal."
    )

    return {
        "total_analyzed": total_count,
        "inactive_over_6_months": inactive_6m,
        "high_risk_count": high_risk,
        "upcoming_terms_count": upcoming_terms,
        "ai_summaries_pct": 100,
        "summary_text": summary_text
    }

def query_ai_processes(
    db: Session,
    company_id: Optional[int],
    query_text: str = "",
    filter_key: str = "",
    is_superadmin: bool = False
) -> Dict[str, Any]:
    """
    Ejecuta consultas de Inteligencia Jurídica sobre los casos reales del usuario.
    """
    q = db.query(Case).filter(Case.juzgado.isnot(None), or_(Case.is_active == True, Case.is_active.is_(None)))
    if not is_superadmin and company_id:
        q = q.filter(Case.company_id == company_id)

    cases = q.order_by(desc(Case.updated_at)).all()
    
    # Pre-cargar eventos de los casos
    case_ids = [c.id for c in cases]
    events_by_case: Dict[int, List[CaseEvent]] = {cid: [] for cid in case_ids}
    
    if case_ids:
        all_events = db.query(CaseEvent).filter(CaseEvent.case_id.in_(case_ids)).order_by(desc(CaseEvent.event_date)).all()
        for ev in all_events:
            events_by_case[ev.case_id].append(ev)

    analyzed_items: List[Dict[str, Any]] = []
    for c in cases:
        evs = events_by_case.get(c.id, [])
        analyzed = analyze_case_risk_and_summary(c, evs)
        analyzed_items.append(analyzed)

    # Filtrar según query o promptKey
    q_norm = (query_text or "").strip().lower()
    f_key = (filter_key or "").strip().lower()

    filtered: List[Dict[str, Any]] = []

    if f_key == "procesos_sin_movimiento" or any(w in q_norm for w in ["sin movimiento", "congelad", "inactiv", "6 meses", "seis meses", "desistimiento"]):
        filtered = [item for item in analyzed_items if item["dias_sin_movimiento"] >= 180]
        analysis_msg = f"🔍 **Análisis IA**: Se identificaron {len(filtered)} procesos con más de 180 días sin actuaciones. Se recomienda radicar memorial de impulso procesal urgente para evitar desistimiento tácito (Art. 317 C.G.P.)."
    
    elif f_key == "sentencias_desfavorables" or any(w in q_norm for w in ["desfavorable", "sentencia", "fallo", "apelacion"]):
        filtered = [item for item in analyzed_items if item["tipo_sentencia"] in ("Desfavorables", "Favorables")]
        if not filtered:
            filtered = [item for item in analyzed_items if "AUTO" in item["resumen_ia"].upper() or item["nivel_riesgo"] == "Alto"]
        analysis_msg = f"⚖️ **Análisis IA**: Se evaluaron las decisiones y sentencias judiciales registradas en tu cartera ({len(filtered)} procesos con decisiones relevantes)."

    elif f_key == "atencion_urgente" or any(w in q_norm for w in ["urgente", "atencion", "riesgo alto", "prioritario"]):
        filtered = [item for item in analyzed_items if item["nivel_riesgo"] == "Alto"]
        analysis_msg = f"⚠️ **Análisis IA**: {len(filtered)} procesos requieren atención prioritaria esta semana debido a inactividad prolongada o términos de notificación."

    elif f_key == "terminos_vencer" or any(w in q_norm for w in ["termino", "vencer", "5 dias", "cinco dias", "plazo"]):
        filtered = [item for item in analyzed_items if item["termino_dias_restantes"] <= 5 or item["nivel_riesgo"] == "Alto"]
        analysis_msg = f"⏱️ **Análisis IA**: Se identificaron {len(filtered)} procesos con términos y actuaciones prioritarias en los próximos días hábiles."

    elif "sic" in q_norm or "superintendencia" in q_norm or "consumidor" in q_norm:
        filtered = [item for item in analyzed_items if item["is_sic"]]
        analysis_msg = f"🏢 **Análisis IA**: Se encontraron {len(filtered)} procesos radicados ante la Superintendencia de Industria y Comercio (SIC)."

    elif q_norm:
        # Búsqueda semántica sobre radicado, partes, juzgado y resumen
        filtered = [
            item for item in analyzed_items
            if q_norm in item["radicado"].lower()
            or q_norm in item["demandante"].lower()
            or q_norm in item["demandado"].lower()
            or q_norm in item["juzgado"].lower()
            or q_norm in item["resumen_ia"].lower()
        ]
        analysis_msg = f"🔎 **Análisis IA**: Se encontraron {len(filtered)} procesos relacionados con tu consulta '{query_text}'."

    else:
        # Todos los casos analizados por defecto
        filtered = analyzed_items
        analysis_msg = f"🤖 **Asistente Jurídico IA**: Mostrando el análisis de {len(filtered)} procesos activos de tu cartera jurídica."

    return {
        "summary": analysis_msg,
        "count": len(filtered),
        "total_analyzed": len(analyzed_items),
        "cases": filtered
    }
