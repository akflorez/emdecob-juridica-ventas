import fitz # PyMuPDF
import io
import re
from datetime import datetime

def generate_sic_actuacion_pdf(
    radicado: str,
    demandante: str,
    demandado: str,
    cedula: str = None,
    actuacion: str = "",
    fecha: str = "",
    detalle: str = "",
    estado: str = "",
    despacho: str = ""
) -> bytes:
    """
    Genera documentos judiciales oficiales diferenciados según la naturaleza exacta
    de la actuación (Auto/Providencia, Certificado RUES, Memorial, Ingreso a Despacho, Presentación).
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792) # Standard Letter size
    
    act_upper = (actuacion or "").upper()
    det_upper = (detalle or "").upper()
    
    # Determinar el tipo específico de documento
    doc_type = "CONSTANCIA"
    header_color = (0.08, 0.18, 0.38) # Dark Navy
    badge_fill = (0.92, 0.95, 1.0)
    badge_text = "CONSTANCIA DE ACTUACIÓN PROCESAL"
    
    if "AUTO" in act_upper or "DECISION" in act_upper or "AUTO" in det_upper:
        doc_type = "AUTO"
        header_color = (0.05, 0.15, 0.35)
        # Extraer número de auto si existe
        auto_match = re.search(r'AUTO\s*(?:NO\.?|NÚMERO)?\s*([0-9]+)', det_upper)
        auto_num = auto_match.group(1) if auto_match else ""
        badge_text = f"PROVIDENCIA JUDICIAL - AUTO No. {auto_num}" if auto_num else "PROVIDENCIA JUDICIAL - AUTO DE TRÁMITE"
    elif "RUES" in act_upper or "CERTIFICADO" in act_upper:
        doc_type = "RUES"
        header_color = (0.05, 0.35, 0.20) # Greenish / Registry
        badge_fill = (0.92, 0.98, 0.94)
        badge_text = "CERTIFICADO DE VERIFICACIÓN REGISTRO RUES"
    elif "MEMORIAL" in act_upper or "ESCRITO" in act_upper:
        doc_type = "MEMORIAL"
        header_color = (0.35, 0.18, 0.05) # Amber/Brownish
        badge_fill = (0.99, 0.96, 0.92)
        badge_text = "MEMORIAL PROCESAL / ESCRITO DE PARTE"
    elif "PRESENTACION" in act_upper or "RADICACION" in act_upper:
        doc_type = "PRESENTACION"
        header_color = (0.15, 0.20, 0.40)
        badge_text = "ACTA DE PRESENTACIÓN Y RADICACIÓN DE DEMANDA"
    elif "DESPACHO" in act_upper or "INGRESO" in act_upper:
        doc_type = "DESPACHO"
        header_color = (0.20, 0.20, 0.30)
        badge_text = "CONSTANCIA DE INGRESO Y PASO AL DESPACHO"

    # 1. Header Banner
    rect_header = fitz.Rect(36, 36, 576, 96)
    page.draw_rect(rect_header, color=header_color, fill=(0.96, 0.97, 0.99), width=1.5)
    
    page.insert_text(fitz.Point(50, 56), "REPÚBLICA DE COLOMBIA", fontsize=8.5, fontname="helv", color=(0.4, 0.4, 0.4))
    page.insert_text(fitz.Point(50, 72), "SUPERINTENDENCIA DE INDUSTRIA Y COMERCIO", fontsize=12, fontname="helv", color=header_color)
    page.insert_text(fitz.Point(50, 88), "DELEGATURA PARA ASUNTOS JURISDICCIONALES • EXPEDIENTE ELECTRÓNICO", fontsize=8, fontname="helv", color=(0.3, 0.4, 0.5))

    # Badge de tipo de documento
    rect_badge = fitz.Rect(36, 106, 576, 132)
    page.draw_rect(rect_badge, color=header_color, fill=badge_fill, width=1)
    page.insert_text(fitz.Point(50, 123), badge_text, fontsize=9.5, fontname="helv", color=header_color)

    # 2. Metadata Box
    rect_body = fitz.Rect(36, 142, 576, 275)
    page.draw_rect(rect_body, color=(0.8, 0.82, 0.88), fill=(0.98, 0.98, 0.99), width=1)
    
    page.insert_text(fitz.Point(50, 162), "RADICADO SIC:", fontsize=9, fontname="helv", color=header_color)
    page.insert_text(fitz.Point(175, 162), f"{radicado}", fontsize=10.5, fontname="helv", color=(0, 0, 0))
    
    page.insert_text(fitz.Point(50, 184), "TRÁMITE / ASUNTO:", fontsize=9, fontname="helv", color=header_color)
    page.insert_text(fitz.Point(175, 184), "DEMANDA PROTECCIÓN AL CONSUMIDOR JURISDICCIONAL", fontsize=8.5, fontname="helv", color=(0.1, 0.1, 0.1))
    
    dem_text = f"{demandante}" + (f" (C.C. {cedula})" if cedula and cedula != "None" else "")
    page.insert_text(fitz.Point(50, 206), "DEMANDANTE / ACCIONANTE:", fontsize=9, fontname="helv", color=header_color)
    page.insert_text(fitz.Point(175, 206), dem_text[:55], fontsize=8.5, fontname="helv", color=(0, 0, 0))
    
    page.insert_text(fitz.Point(50, 228), "DEMANDADO / ACCIONADO:", fontsize=9, fontname="helv", color=header_color)
    page.insert_text(fitz.Point(175, 228), f"{demandado}"[:55], fontsize=8.5, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 250), "ESTADO DEL PROCESO:", fontsize=9, fontname="helv", color=header_color)
    page.insert_text(fitz.Point(175, 250), (estado or "En Trámite Jurisdiccional")[:55], fontsize=8.5, fontname="helv", color=(0.7, 0.2, 0.1))

    # 3. Document Content Box (Differentiated by Type)
    rect_content = fitz.Rect(36, 290, 576, 715)
    page.draw_rect(rect_content, color=header_color, fill=(1.0, 1.0, 1.0), width=1)
    
    # Title Bar inside content
    page.draw_rect(fitz.Rect(36, 290, 576, 318), color=header_color, fill=header_color)
    
    if doc_type == "AUTO":
        page.insert_text(fitz.Point(50, 309), "TEXTO DE LA PROVIDENCIA / AUTO JUDICIAL", fontsize=9.5, fontname="helv", color=(1, 1, 1))
        
        page.insert_text(fitz.Point(50, 345), f"Decisión / Providencia:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 345), f"{actuacion}", fontsize=9.5, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 370), f"Fecha de Notificación:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 370), f"{fecha}", fontsize=9.5, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 395), f"Autoridad Emisora:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 395), "Delegatura para Asuntos Jurisdiccionales - SIC", fontsize=9, fontname="helv", color=(0, 0, 0))

        content_body = (
            f"En la fecha señalada, el Despacho de la Delegatura para Asuntos Jurisdiccionales profiere la presente decisión dentro del proceso con radicado {radicado}.\n\n"
            f"RESUMEN Y DISPOSICIONES:\n"
            f"• Actuación: {actuacion}\n"
            f"• Detalles y Anotación Oficial: {detalle}\n\n"
            f"NOTIFÍQUESE Y CÚMPLASE.\n"
            f"Superintendencia de Industria y Comercio\n"
            f"Grupo de Trabajo y Secretaría General"
        )

    elif doc_type == "RUES":
        page.insert_text(fitz.Point(50, 309), "CONSTANCIA DE VERIFICACIÓN REGISTRO MERCANTIL (RUES)", fontsize=9.5, fontname="helv", color=(1, 1, 1))
        
        page.insert_text(fitz.Point(50, 345), "Entidad Consultada:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 345), "Registro Único Empresarial y Social (RUES) / Cámaras de Comercio", fontsize=9, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 370), "Fecha de Incorporación:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 370), f"{fecha}", fontsize=9.5, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 395), "Sociedad / Sujeto:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 395), f"{demandado}", fontsize=9, fontname="helv", color=(0, 0, 0))

        content_body = (
            f"Se deja constancia procesal de la incorporación al expediente del Certificado de Existencia y Representación Legal (RUES) del demandado {demandado}.\n\n"
            f"INFORMACIÓN DEL REGISTRO:\n"
            f"• Trámite: Demanda de Protección al Consumidor Jurisdiccional\n"
            f"• Anotación en Secretaría: {detalle}\n"
            f"• Objeto: Verificación de personería jurídica, facultades de representación y domicilio judicial de la demandada."
        )

    elif doc_type == "MEMORIAL":
        page.insert_text(fitz.Point(50, 309), "REGISTRO DE MEMORIAL / SOLICITUD DE PARTE", fontsize=9.5, fontname="helv", color=(1, 1, 1))
        
        page.insert_text(fitz.Point(50, 345), "Tipo de Escrito:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 345), "MEMORIAL DE PARTE (Solicitud / Pronunciamiento)", fontsize=9, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 370), "Fecha de Radicación:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 370), f"{fecha}", fontsize=9.5, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 395), "Radicador / Solicitante:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 395), f"{demandante}", fontsize=9, fontname="helv", color=(0, 0, 0))

        content_body = (
            f"Se certifica la recepción y radicación electrónica del memorial presentado por la parte accionante {demandante} dentro del expediente {radicado}.\n\n"
            f"CONTENIDO DEL REGISTRO:\n"
            f"• Anotación Oficial: {detalle}\n"
            f"• Trámite: Demanda de Protección al Consumidor Jurisdiccional\n"
            f"• Estado: Incorporado al expediente para decisión del despacho."
        )

    elif doc_type == "PRESENTACION":
        page.insert_text(fitz.Point(50, 309), "ACTA DE PRESENTACIÓN Y REPARTO DE DEMANDA", fontsize=9.5, fontname="helv", color=(1, 1, 1))
        
        page.insert_text(fitz.Point(50, 345), "Acción Judicial:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 345), "Demanda de Protección al Consumidor en Ejercicio de Funciones Jurisdiccionales", fontsize=8.5, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 370), "Fecha de Presentación:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 370), f"{fecha}", fontsize=9.5, fontname="helv", color=(0, 0, 0))

        content_body = (
            f"En la fecha {fecha} se radicó formalmente la demanda de protección al consumidor por parte de {demandante} en contra de {demandado}.\n\n"
            f"DATOS DE RADICACIÓN:\n"
            f"• Radicado Asignado: {radicado}\n"
            f"• Anotación de Ingreso: {detalle}\n"
            f"• Autoridad: Superintendencia de Industria y Comercio - Delegatura Jurisdiccional."
        )

    else:
        page.insert_text(fitz.Point(50, 309), "CONSTANCIA DE SECRETARÍA / EXPEDIENTE", fontsize=9.5, fontname="helv", color=(1, 1, 1))
        
        page.insert_text(fitz.Point(50, 345), "Actuación:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 345), f"{actuacion}", fontsize=9.5, fontname="helv", color=(0, 0, 0))

        page.insert_text(fitz.Point(50, 370), "Fecha de Registro:", fontsize=9.5, fontname="helv", color=header_color)
        page.insert_text(fitz.Point(175, 370), f"{fecha}", fontsize=9.5, fontname="helv", color=(0, 0, 0))

        content_body = (
            f"Se deja constancia de la actuación procesal registrada en el expediente {radicado}.\n\n"
            f"DETALLES DE LA ACTUACIÓN:\n"
            f"• Anotación: {detalle}\n"
            f"• Sujetos Procesales: {demandante} vs. {demandado}\n"
            f"• Despacho: Superintendencia de Industria y Comercio."
        )

    # Insertar el cuerpo de texto formateado
    text_rect = fitz.Rect(50, 420, 560, 690)
    page.insert_textbox(text_rect, content_body, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15), align=0)
    
    # 4. Footer
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    page.insert_text(fitz.Point(50, 745), f"Documento oficial expedido a través del Sistema JURICOB • Generado el {now_str}", fontsize=7.5, fontname="helv", color=(0.45, 0.45, 0.45))
    page.insert_text(fitz.Point(50, 758), "Portal Oficial SIC: https://consultatramites.sic.gov.co/consulta-externa", fontsize=7.5, fontname="helv", color=(0.1, 0.3, 0.7))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes
