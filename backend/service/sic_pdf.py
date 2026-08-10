import fitz # PyMuPDF
import io
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
    Genera un documento PDF oficial con membrete y estructura judicial para actuaciones
    de la Superintendencia de Industria y Comercio (Delegatura para Asuntos Jurisdiccionales).
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792) # Standard Letter size (8.5 x 11 in)
    
    # 1. Header Banner
    rect_header = fitz.Rect(36, 36, 576, 100)
    page.draw_rect(rect_header, color=(0.08, 0.18, 0.38), fill=(0.94, 0.96, 1.0), width=1.5)
    
    page.insert_text(fitz.Point(50, 58), "REPÚBLICA DE COLOMBIA", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
    page.insert_text(fitz.Point(50, 75), "SUPERINTENDENCIA DE INDUSTRIA Y COMERCIO", fontsize=13, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(50, 92), "DELEGATURA PARA ASUNTOS JURISDICCIONALES • EXPEDIENTE ELECTRÓNICO", fontsize=8.5, fontname="helv", color=(0.2, 0.4, 0.6))
    
    # 2. Metadata Box
    rect_body = fitz.Rect(36, 115, 576, 285)
    page.draw_rect(rect_body, color=(0.75, 0.8, 0.88), fill=(0.98, 0.98, 0.99), width=1)
    
    # Left column: labels, Right column: values
    page.insert_text(fitz.Point(50, 138), "RADICADO SIC:", fontsize=9.5, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(175, 138), f"{radicado}", fontsize=11, fontname="helv", color=(0, 0, 0))
    
    page.insert_text(fitz.Point(50, 162), "TRÁMITE / ASUNTO:", fontsize=9.5, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(175, 162), "DEMANDA PROTECCIÓN AL CONSUMIDOR JURISDICCIONAL", fontsize=9, fontname="helv", color=(0.1, 0.1, 0.1))
    
    dem_text = f"{demandante}" + (f" (C.C. {cedula})" if cedula and cedula != "None" else "")
    page.insert_text(fitz.Point(50, 186), "DEMANDANTE / ACCIONANTE:", fontsize=9.5, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(175, 186), dem_text[:55], fontsize=9, fontname="helv", color=(0, 0, 0))
    
    page.insert_text(fitz.Point(50, 210), "DEMANDADO / ACCIONADO:", fontsize=9.5, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(175, 210), f"{demandado}"[:55], fontsize=9, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 234), "AUTORIDAD JUDICIAL:", fontsize=9.5, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(175, 234), (despacho or "Superintendencia de Industria y Comercio - SIC")[:55], fontsize=9, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 258), "ESTADO PROCESAL:", fontsize=9.5, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(175, 258), (estado or "En Trámite Jurisdiccional")[:55], fontsize=9, fontname="helv", color=(0.7, 0.2, 0.1))

    # 3. Actuation Body Section
    rect_act = fitz.Rect(36, 305, 576, 710)
    page.draw_rect(rect_act, color=(0.08, 0.18, 0.38), fill=(1.0, 1.0, 1.0), width=1)
    
    # Section Header Bar
    page.draw_rect(fitz.Rect(36, 305, 576, 335), color=(0.08, 0.18, 0.38), fill=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(50, 325), "CONSTANCIA Y CONTENIDO DE LA ACTUACIÓN JUDICIAL", fontsize=10, fontname="helv", color=(1, 1, 1))

    page.insert_text(fitz.Point(50, 360), "Actuación:", fontsize=10, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(140, 360), f"{actuacion}", fontsize=10, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 388), "Fecha:", fontsize=10, fontname="helv", color=(0.08, 0.18, 0.38))
    page.insert_text(fitz.Point(140, 388), f"{fecha}", fontsize=10, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 420), "Anotación / Registro Oficial:", fontsize=10, fontname="helv", color=(0.08, 0.18, 0.38))
    
    # Formatear detalle con saltos de línea claros
    formatted_detail = detalle or "Actuación procesal registrada formalmente en el sistema de la Superintendencia de Industria y Comercio."
    if " | " in formatted_detail:
        formatted_detail = formatted_detail.replace(" | ", "\n• ")
        if not formatted_detail.startswith("• "):
            formatted_detail = "• " + formatted_detail

    text_rect = fitz.Rect(50, 440, 560, 680)
    page.insert_textbox(text_rect, formatted_detail, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15), align=0)
    
    # 4. Footer
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    page.insert_text(fitz.Point(50, 745), f"Documento oficial de consulta expedido a través de JURICOB • Generado el {now_str}", fontsize=8, fontname="helv", color=(0.45, 0.45, 0.45))
    page.insert_text(fitz.Point(50, 758), "Verificación oficial: https://consultatramites.sic.gov.co/consulta-externa", fontsize=8, fontname="helv", color=(0.1, 0.3, 0.7))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes
