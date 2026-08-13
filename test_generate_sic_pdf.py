import fitz # PyMuPDF
import io

def generate_sic_pdf(radicado, demandante, demandado, cedula, actuacion, fecha, detalle, estado):
    doc = fitz.open()
    page = doc.new_page(width=612, height=792) # Standard Letter size
    
    # Draw header banner
    rect_header = fitz.Rect(36, 36, 576, 95)
    page.draw_rect(rect_header, color=(0.1, 0.2, 0.45), fill=(0.94, 0.96, 1.0), width=1.5)
    
    # Header text
    page.insert_text(fitz.Point(50, 60), "SUPERINTENDENCIA DE INDUSTRIA Y COMERCIO", fontsize=13, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(50, 78), "DELEGATURA PARA ASUNTOS JURISDICCIONALES - CONSTANCIA OFICIAL", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
    
    # Process metadata box
    rect_body = fitz.Rect(36, 115, 576, 290)
    page.draw_rect(rect_body, color=(0.8, 0.8, 0.8), fill=(0.98, 0.98, 0.98), width=1)
    
    page.insert_text(fitz.Point(50, 140), f"RADICADO SIC:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(180, 140), f"{radicado}", fontsize=11, fontname="helv", color=(0, 0, 0))
    
    page.insert_text(fitz.Point(50, 165), f"TRÁMITE:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(180, 165), "DEMANDA PROTECCIÓN AL CONSUMIDOR JURISDICCIONAL", fontsize=9, fontname="helv", color=(0, 0, 0))
    
    page.insert_text(fitz.Point(50, 190), f"DEMANDANTE:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(180, 190), f"{demandante} (C.C. {cedula})", fontsize=9, fontname="helv", color=(0, 0, 0))
    
    page.insert_text(fitz.Point(50, 215), f"DEMANDADO:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(180, 215), f"{demandado}", fontsize=9, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 240), f"ESTADO ACTUAL:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(180, 240), f"{estado}", fontsize=9, fontname="helv", color=(0.7, 0.2, 0.1))

    page.insert_text(fitz.Point(50, 265), f"AUTORIDAD / DESPACHO:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(180, 265), "Superintendencia de Industria y Comercio - SIC", fontsize=9, fontname="helv", color=(0, 0, 0))

    # Actuacion Section
    rect_act = fitz.Rect(36, 310, 576, 680)
    page.draw_rect(rect_act, color=(0.1, 0.2, 0.45), fill=(1.0, 1.0, 1.0), width=1)
    
    page.draw_rect(fitz.Rect(36, 310, 576, 340), color=(0.1, 0.2, 0.45), fill=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(50, 330), "DETALLE DE LA ACTUACIÓN / CONSTANCIA DOCUMENTAL", fontsize=10, fontname="helv", color=(1, 1, 1))

    page.insert_text(fitz.Point(50, 370), f"Actuación:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(140, 370), f"{actuacion}", fontsize=10, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 400), f"Fecha:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    page.insert_text(fitz.Point(140, 400), f"{fecha}", fontsize=10, fontname="helv", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 435), f"Contenido / Anotación:", fontsize=10, fontname="helv", color=(0.1, 0.2, 0.45))
    
    # Wrap text in content area
    text_rect = fitz.Rect(50, 455, 560, 640)
    page.insert_textbox(text_rect, detalle, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15), align=0)
    
    # Footer
    page.insert_text(fitz.Point(50, 750), "Documento generado por el Sistema Jurídico JURICOB - Conexión Oficial SIC", fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))
    page.insert_text(fitz.Point(50, 762), "Portal Oficial: https://consultatramites.sic.gov.co/consulta-externa", fontsize=8, fontname="helv", color=(0.2, 0.4, 0.8))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

# Test generating a document
pdf_data = generate_sic_pdf(
    radicado="26-64018",
    demandante="ERICA YOHANA RAMIREZ PEREA",
    demandado="MOTO EXPERIENCIA SAS",
    cedula="1143957035",
    actuacion="DECISION - TRASLADO SECRETARIA GENERAL",
    fecha="16/03/2026 05:41",
    detalle="Trámite: DEMANDA PROTECCIÓN AL CONSUMIDOR JURISDICCIONAL\nTipo de Actuación: TR (Traslado)\nDestinatario: PEDRO ALEJANDRO NIÑO ROA\nDecisión: AUTO No. 28427 de Fecha 2026-03-13\n\nEl Despacho de la Delegatura para Asuntos Jurisdiccionales de la Superintendencia de Industria y Comercio informa el traslado a Secretaría General conforme al Auto No. 28427 en el marco del proceso de protección al consumidor.",
    estado="ALLANAMIENTO CAMBIO DE VEHÍCULO"
)

with open("test_sic_output.pdf", "wb") as f:
    f.write(pdf_data)

print(f"Generated test_sic_output.pdf ({len(pdf_data)} bytes) successfully!")
