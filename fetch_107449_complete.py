import asyncio
from playwright.async_api import async_playwright
from sqlalchemy import create_engine, text
import hashlib
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url_db = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url_db)

def sha256_obj(obj):
    raw = json.dumps(obj, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

async def fetch_107449_complete():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-CO",
            timezone_id="America/Bogota"
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        captured_content = []

        async def on_resp(res):
            if "apiexternotramites.sic.gov.co/consulta-externa/v1/radicados" in res.url:
                try:
                    data = await res.json()
                    print(f"🔥 HTTP Status {res.status} de la API SIC! URL: {res.url[:90]}")
                    if data.get("success") and data.get("data"):
                        content = data["data"].get("content", [])
                        print(f"🎉 ¡TOTAL ACTUACIONES EXTRAÍDAS PARA 25-107449: {len(content)}!")
                        captured_content.extend(content)
                except Exception as e:
                    print("Error JSON:", e)

        page.on("response", on_resp)

        print("🌐 Navegando a SIC...")
        await page.goto("https://consultatramites.sic.gov.co/consulta-externa", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Entendido
        ent = page.locator('button:has-text("Entendido")')
        if await ent.count() > 0:
            await ent.first.click()
            await page.wait_for_timeout(500)

        # Año 2025
        print("📅 Seleccionando año 2025...")
        await page.locator('#anio').click()
        await page.wait_for_timeout(500)
        await page.locator('li:has-text("2025")').first.click()
        await page.wait_for_timeout(500)

        # Número 107449
        print("🔢 Escribiendo número 107449...")
        await page.locator('#numero').fill("107449")
        await page.wait_for_timeout(500)

        # Cédula
        await page.locator('p-select[formcontrolname="documentType"]').click()
        await page.wait_for_timeout(500)
        await page.locator('.p-select-overlay li').first.click()
        await page.wait_for_timeout(500)
        await page.locator('#identificationNumber').fill("1004826465")
        await page.wait_for_timeout(1000)

        # Esperar botón habilitado
        print("⏳ Esperando activación del botón Consultar...")
        for sec in range(12):
            disabled = await page.locator('button:has-text("Consultar")').get_attribute("disabled")
            if disabled is None:
                print(f"🎉 ¡BOTÓN CONSULTAR HABILITADO EN EL SEGUNDO {sec+1}!")
                break
            await page.wait_for_timeout(1000)

        print("🔘 Click Consultar...")
        await page.locator('button:has-text("Consultar")').click()

        for _ in range(15):
            if captured_content:
                break
            await page.wait_for_timeout(1000)

        await browser.close()

        if captured_content:
            print(f"\n Mapeando {len(captured_content)} actuaciones...")
            acts = []
            for item in captured_content:
                raw_fecha = str(item.get("fechaRadicado") or item.get("fecha") or "").strip()
                fecha_str = ""
                if raw_fecha:
                    if "/" in raw_fecha:
                        parts = raw_fecha.split()[0].split("/")
                        if len(parts) == 3:
                            if len(parts[2]) == 4:
                                fecha_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                            else:
                                fecha_str = f"20{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    elif "-" in raw_fecha:
                        fecha_str = raw_fecha[:10]

                act_title = (item.get("actuacionRadicado") or item.get("actuacion") or "Actuación SIC").strip()
                tramite = (item.get("tramiteRadicado") or item.get("tramite") or "DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL").strip()
                solicitante = (item.get("solicitanteDestinatario") or item.get("solicitante") or "").strip()
                tipo = (item.get("tipoRadicado") or item.get("tipo") or "").strip()

                anot_parts = [f"Trámite: {tramite}"]
                if tipo: anot_parts.append(f"Tipo: {tipo}")
                if solicitante: anot_parts.append(f"Sujeto: {solicitante}")

                acts.append({
                    "fecha": fecha_str,
                    "title": act_title,
                    "detail": " | ".join(anot_parts)
                })

            acts.sort(key=lambda x: x["fecha"], reverse=True)

            cid = 2563 # Caso ID para 25-107449
            with engine.connect() as conn:
                conn.execute(text(f"DELETE FROM case_events WHERE case_id = {cid};"))
                for a in acts:
                    ev_hash = sha256_obj(a)
                    conn.execute(text("""
                        INSERT INTO case_events (case_id, company_id, event_date, title, detail, event_hash, con_documentos)
                        VALUES (:cid, 3, :date, :title, :detail, :hash, false)
                    """), {
                        "cid": cid,
                        "date": a["fecha"],
                        "title": a["title"],
                        "detail": a["detail"],
                        "hash": ev_hash
                    })

                newest = acts[0]["fecha"]
                oldest = acts[-1]["fecha"]
                conn.execute(text("""
                    UPDATE cases 
                    SET ultima_actuacion = :newest,
                        fecha_radicacion = :oldest,
                        has_documents = false,
                        is_active = true,
                        last_check_at = NOW()
                    WHERE id = :cid;
                """), {"newest": newest, "oldest": oldest, "cid": cid})
                conn.commit()
                print(f"✨ ¡TODAS LAS {len(acts)} ACTUACIONES REALES PARA CASO 25-107449 GUARDADAS EN POSTGRESQL!")
                for idx, a in enumerate(acts):
                    print(f"   [{idx+1}] {a['fecha']} | {a['title']} | {a['detail'][:60]}...")
        else:
            print("❌ No se pudieron capturar las actuaciones")

if __name__ == "__main__":
    asyncio.run(fetch_107449_complete())
