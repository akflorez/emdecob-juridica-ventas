import time
import json
import hashlib
from datetime import datetime, date
from sqlalchemy.orm import Session
from backend.models import Case, CaseEvent, CasePublication, CaseSearchSourceResult, User
from backend.services.judicial_sources import CONNECTORS
from backend.services.judicial_sources.normalizer import normalize_case_result

# Configuration flags for fallback connectors
FALLBACK_TYBA_ENABLED = True
FALLBACK_SIUGJ_ENABLED = False
FALLBACK_SAMAI_ENABLED = False

async def search_radicado_with_fallbacks(
    radicado: str,
    company_id: int,
    db: Session,
    current_user: User,
    force: bool = False
) -> dict:
    """
    Search engine for radicados:
    1. Clean the radicado string.
    2. Enforce company_id (multi-tenancy) and current_user validation.
    3. Query the main Rama Judicial principal source first.
    4. If not found or error, query alternative official sources (Fase 1: Publicaciones Procesales).
    5. Save lookup trace to CaseSearchSourceResult.
    6. Normalize and upsert case details, events, and publications if found in alternative source.
    """
    from backend.main import clean_str, sha256_obj, parse_fecha
    
    radicado_clean = clean_str(radicado)
    if not radicado_clean:
        return {"status": "error", "message": "El radicado no es válido o está vacío."}
        
    # Enforce company_id constraints
    if current_user and (current_user.is_superadmin or (current_user.is_admin and not current_user.company_id)):
        if not company_id:
            return {"status": "error", "message": "Selecciona una empresa para asociar el radicado."}
    else:
        if current_user:
            company_id = current_user.company_id
        if not company_id:
            return {"status": "error", "message": "Empresa no especificada o usuario sin empresa asignada."}

    # If force=False, verify if case already exists in database
    if not force:
        existing_case = db.query(Case).filter(
            Case.company_id == company_id,
            Case.radicado == radicado_clean
        ).first()
        if existing_case and not existing_case.encontrado_en_fuente_alternativa:
            # Case exists and was verified by Rama Judicial principal, return it directly
            return {
                "status": "found",
                "source": "rama_judicial",
                "case": existing_case
            }

    # Track search order
    source_order = 1
    
    # ----------------------------------------------------
    # STEP 1: Query Rama Judicial principal
    # ----------------------------------------------------
    start_time = time.time()
    
    # Log lookup start in CaseSearchSourceResult
    principal_log = CaseSearchSourceResult(
        company_id=company_id,
        radicado=radicado_clean,
        fuente="RAMA_JUDICIAL",
        tipo_fuente="rama_judicial",
        url="https://procesojudicial.ramajudicial.gov.co/Justicia21/Procesos.aspx",
        encontrado=False,
        confianza=0,
        estado="pending",
        mensaje="Iniciando consulta en Rama Judicial principal.",
        source_order=source_order,
        force=force,
        requiere_revision=False,
        created_by=current_user.id if current_user else None,
        created_at=datetime.utcnow()
    )
    db.add(principal_log)
    db.flush()
    
    rama_found = False
    rama_case = None
    rama_error = None
    http_status = 200
    
    try:
        from backend.main import validar_radicado_completo
        result = await validar_radicado_completo(radicado_clean, db, is_new_import=True)
        
        duration_ms = int((time.time() - start_time) * 1000)
        principal_log.duration_ms = duration_ms
        
        if result and result.get("found") and result.get("case"):
            rama_case = result.get("case")
            rama_found = True
            
            # Ensure company_id is correctly assigned to the case
            if rama_case.company_id != company_id:
                rama_case.company_id = company_id
                db.flush()
                
            principal_log.case_id = rama_case.id
            principal_log.encontrado = True
            principal_log.confianza = 100
            principal_log.estado = "success"
            principal_log.mensaje = "Caso encontrado en Rama Judicial principal."
            db.commit()
            
            return {
                "status": "found",
                "source": "rama_judicial",
                "case": rama_case
            }
        else:
            principal_log.estado = "not_found"
            principal_log.mensaje = "No se encontraron registros en Rama Judicial principal."
            db.commit()
            
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        rama_error = str(e)
        principal_log.duration_ms = duration_ms
        principal_log.estado = "error"
        principal_log.error_type = type(e).__name__
        principal_log.mensaje = f"Error al consultar Rama Judicial principal: {rama_error}"
        http_status = 500
        db.commit()

    # ----------------------------------------------------
    # STEP 2: Query Alternative Official Sources (Fallback)
    # ----------------------------------------------------
    # Define active sources list for Fase 1
    active_sources = ["PUBLICACIONES_PROCESALES"]
    if FALLBACK_TYBA_ENABLED:
        active_sources.append("TYBA")
    if FALLBACK_SIUGJ_ENABLED:
        active_sources.append("SIUGJ")
    if FALLBACK_SAMAI_ENABLED:
        active_sources.append("SAMAI")
        
    for alt_source in active_sources:
        source_order += 1
        connector = CONNECTORS.get(alt_source)
        if not connector or not connector.supports(radicado_clean):
            continue
            
        alt_start_time = time.time()
        
        alt_log = CaseSearchSourceResult(
            company_id=company_id,
            radicado=radicado_clean,
            fuente=alt_source,
            tipo_fuente=alt_source.lower(),
            url=connector.config.get("base_url", ""),
            encontrado=False,
            confianza=0,
            estado="pending",
            mensaje=f"Iniciando consulta alternativa en {alt_source}.",
            source_order=source_order,
            force=force,
            requiere_revision=False,
            created_by=current_user.id if current_user else None,
            created_at=datetime.utcnow()
        )
        db.add(alt_log)
        db.flush()
        
        try:
            res = connector.search_case(radicado_clean)
            alt_duration = int((time.time() - alt_start_time) * 1000)
            alt_log.duration_ms = alt_duration
            
            if res.get("status") == "success":
                # Found in alternative source!
                raw_data = res.get("data", {})
                normalized = normalize_case_result(res, alt_source)
                
                # Determine Match Confidence & requiere_revision
                conf_score = normalized["confianza_busqueda"]
                req_revision = normalized["requiere_revision"]
                
                if conf_score >= 85:
                    req_revision = False
                elif 70 <= conf_score < 85:
                    req_revision = True
                else:
                    # Weak match: log but do not save case
                    alt_log.estado = "unverified"
                    alt_log.mensaje = "Coincidencia débil. No se confirma el caso."
                    alt_log.confianza = conf_score
                    db.commit()
                    continue
                
                # Truncate raw response to 50k characters limit
                raw_resp_str = json.dumps(res)[:50000]
                
                alt_log.encontrado = True
                alt_log.confianza = conf_score
                alt_log.estado = "success"
                alt_log.requiere_revision = req_revision
                alt_log.mensaje = f"Encontrado en fuente alternativa {alt_source}."
                alt_log.datos_extraidos_json = json.dumps(normalized)
                alt_log.raw_response = raw_resp_str
                
                # Upsert Case
                c = db.query(Case).filter(
                    Case.company_id == company_id,
                    Case.radicado == radicado_clean
                ).first()
                
                is_new_case = False
                if not c:
                    c = Case(
                        radicado=radicado_clean,
                        company_id=company_id,
                        user_id=current_user.id if current_user else None
                    )
                    db.add(c)
                    db.flush()
                    is_new_case = True
                
                # Update core fields only if they are currently empty (No sobrescribir información buena)
                c.despacho = c.despacho or normalized["despacho"]
                c.juzgado = c.juzgado or normalized["despacho"]
                c.demandante = c.demandante or normalized["demandante"]
                c.demandado = c.demandado or normalized["demandado"]
                c.clase_proceso = c.clase_proceso or normalized["clase_proceso"]
                c.tipo_proceso = c.tipo_proceso or normalized["tipo_proceso"]
                c.estado = c.estado or normalized["estado"]
                c.departamento = c.departamento or normalized["departamento"]
                c.municipio = c.municipio or normalized["municipio"]
                c.ponente_juez = c.ponente_juez or normalized["ponente_juez"]
                c.ubicacion = c.ubicacion or normalized["ubicacion"]
                c.url_fuente = c.url_fuente or normalized["url_fuente"]
                c.fuente_encontrado = c.fuente_encontrado or normalized["origen_fuente"]
                c.metodo_busqueda = c.metodo_busqueda or "fallback_alternative"
                c.confianza_busqueda = conf_score
                c.encontrado_en_fuente_alternativa = True
                c.requiere_revision = req_revision
                
                if not c.fecha_radicacion and normalized["fecha_radicacion"]:
                    c.fecha_radicacion = parse_fecha(normalized["fecha_radicacion"])
                if not c.ultima_actuacion and normalized["fecha_ultima_actuacion"]:
                    c.ultima_actuacion = parse_fecha(normalized["fecha_ultima_actuacion"])
                    
                db.flush()
                
                # Assign case_id to the alternative check log
                alt_log.case_id = c.id
                
                # Save events (actuaciones) if available
                events = connector.search_events(radicado_clean)
                for ev in events:
                    it_alt = {
                        "event_date": ev.get("fecha_actuacion") or ev.get("event_date"),
                        "title": (ev.get("actuacion") or ev.get("title") or "").strip(),
                        "detail": ev.get("anotacion") or ev.get("detail"),
                        "fecha_registro": ev.get("fecha_registro") or ev.get("created_at"),
                    }
                    event_hash = sha256_obj(it_alt)
                    
                    exists_event = db.query(CaseEvent).filter(
                        CaseEvent.case_id == c.id,
                        CaseEvent.event_hash == event_hash
                    ).first()
                    
                    if not exists_event:
                        db.add(CaseEvent(
                            case_id=c.id,
                            company_id=company_id,
                            event_date=it_alt["event_date"],
                            title=it_alt["title"],
                            detail=it_alt["detail"],
                            event_hash=event_hash,
                            con_documentos=False,
                            created_at=datetime.utcnow()
                        ))
                
                # Save publications if available (or convert documents to publications)
                docs = connector.search_documents(radicado_clean)
                for doc in docs:
                    doc_url = doc.get("url_documento") or doc.get("documento_url")
                    source_id = hashlib.md5((doc_url or "").encode()).hexdigest()
                    
                    exists_pub = db.query(CasePublication).filter(
                        CasePublication.case_id == c.id,
                        CasePublication.source_id == source_id
                    ).first()
                    
                    if not exists_pub:
                        fecha_pub_parsed = parse_fecha(doc.get("fecha_publicacion")) if doc.get("fecha_publicacion") else None
                        db.add(CasePublication(
                            case_id=c.id,
                            company_id=company_id,
                            fecha_publicacion=fecha_pub_parsed,
                            tipo_publicacion=doc.get("tipo_documento") or "Publicación Procesal",
                            descripcion=doc.get("nombre_archivo") or "Documento encontrado",
                            documento_url=doc_url,
                            source_url=res.get("url"),
                            source_id=source_id,
                            estado_validacion="validado" if conf_score >= 85 else "requiere_revision",
                            match_score=conf_score,
                            url_fuente_principal=doc_url,
                            validada_por_fuente_principal=True,
                            requiere_revision=req_revision,
                            created_at=datetime.utcnow()
                        ))
                
                # Commit everything
                db.commit()
                
                # Auto queue publications for the case in background to verify further publications
                try:
                    from backend.service.publicaciones import auto_queue_publicaciones_for_case
                    auto_queue_publicaciones_for_case(db, c)
                except Exception as pq_err:
                    print(f"[fallback-search] Warning: auto_queue_publicaciones_for_case failed: {pq_err}")
                
                return {
                    "status": "found_alternative",
                    "source": alt_source.lower(),
                    "case": c,
                    "url_fuente": normalized["url_fuente"],
                    "confidence": conf_score,
                    "requiere_revision": req_revision
                }
            else:
                alt_log.estado = "not_found"
                alt_log.mensaje = res.get("message", "No se encontraron registros en esta fuente.")
                db.commit()
                
        except Exception as alt_err:
            alt_log.duration_ms = int((time.time() - alt_start_time) * 1000)
            alt_log.estado = "error"
            alt_log.error_type = type(alt_err).__name__
            alt_log.mensaje = f"Error al consultar fuente alternativa {alt_source}: {alt_err}"
            db.commit()

    # ----------------------------------------------------
    # STEP 3: Return not_found
    # ----------------------------------------------------
    # Get checked sources names
    checked = ["rama_judicial"] + [s.lower() for s in active_sources]
    return {
        "status": "not_found",
        "message": "No se encontró el radicado en las fuentes oficiales consultadas.",
        "sources_checked": checked
    }
