import os
import sys
import pandas as pd
import paramiko
import requests
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.getcwd())
from ebay_auth import get_token

# ========== CONFIGURAZIONE ==========
SFTP_CONF = {
    "host": "134.209.254.177",
    "user": "root",
    "pass": "Iapqualityparts2025!",
    "path": "/home/aggiorna/upload",
}

EBAY_API_URL = "https://api.ebay.com/ws/api.dll"
SITE_ID = "101"
COMPATIBILITY_LEVEL = "967"
LOG_FILE = "logs/ebay_qty.log"

os.makedirs("logs", exist_ok=True)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
fh = logging.FileHandler(LOG_FILE)
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)


def download_csv():
    """Scarica CSV fornitore da SFTP"""
    transport = None
    try:
        transport = paramiko.Transport((SFTP_CONF["host"], 22))
        transport.connect(username=SFTP_CONF["user"], password=SFTP_CONF["pass"])

        with paramiko.SFTPClient.from_transport(transport) as sftp:
            files = [
                f
                for f in sftp.listdir_attr(SFTP_CONF["path"])
                if f.filename.lower().endswith(".csv")
            ]
            if not files:
                logging.error("Nessun CSV su SFTP")
                return None

            latest = max(files, key=lambda x: x.st_mtime)
            sftp.get(f"{SFTP_CONF['path']}/{latest.filename}", "temp_fornitore.csv")
            logging.info(f"CSV scaricato: {latest.filename}")
            return "temp_fornitore.csv"

    except Exception as e:
        logging.error(f"Errore SFTP: {e}")
        return None
    finally:
        if transport:
            transport.close()


def get_ebay_inventory_multi(token):
    """
    Scarica inventario eBay gestendo SKU duplicati (AISIN, LUK, EXEDY, ecc.)
    Usa un Set per tracciare ItemID già visti ed evitare duplicati
    Ritorna: {SKU: [{'id': ItemID, 'qty': int}, ...]}
    """
    headers = {
        "X-EBAY-API-SITEID": SITE_ID,
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPATIBILITY_LEVEL,
        "X-EBAY-API-CALL-NAME": "GetMyeBaySelling",
        "X-EBAY-API-IAF-TOKEN": token,
        "Content-Type": "text/xml",
    }

    inventory = {}
    itemids_visti = set()  # Previene duplicati ItemID
    page = 1
    total_pages = 1

    logging.info("📥 Download inventario eBay (gestione multi-ID)...")

    while page <= total_pages:
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
        <GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
            <ActiveList>
                <Include>true</Include>
                <Pagination>
                    <EntriesPerPage>200</EntriesPerPage>
                    <PageNumber>{page}</PageNumber>
                </Pagination>
            </ActiveList>
            <DetailLevel>ReturnAll</DetailLevel>
        </GetMyeBaySellingRequest>"""

        try:
            r = requests.post(EBAY_API_URL, data=xml, headers=headers, timeout=60)
            root = ET.fromstring(r.content)
            ns = {"e": "urn:ebay:apis:eBLBaseComponents"}

            if page == 1:
                tp = root.find(".//e:TotalNumberOfPages", ns)
                total_pages = int(tp.text) if tp is not None else 1
                logging.info(f"Pagine totali: {total_pages}")

            for item in root.findall(".//e:Item", ns):
                sku_node = item.find("e:SKU", ns)
                id_node = item.find("e:ItemID", ns)
                qty_node = item.find("e:Quantity", ns)
                sold_node = item.find(".//e:SellingStatus/e:QuantitySold", ns)

                if sku_node is not None and id_node is not None and sku_node.text:
                    itemid = id_node.text

                    # Salta ItemID già processati (evita duplicati API)
                    if itemid in itemids_visti:
                        continue

                    itemids_visti.add(itemid)

                    # Normalizza SKU: "703-14041_IAP QUALITY PARTS" → "703-14041"
                    sku = sku_node.text.split("_")[0].strip()

                    qty_totale = int(qty_node.text) if qty_node is not None else 0
                    qty_venduta = int(sold_node.text) if sold_node is not None else 0
                    qty_disponibile = max(0, qty_totale - qty_venduta)

                    # Aggiunge senza sovrascrivere (gestione duplicati SKU)
                    if sku not in inventory:
                        inventory[sku] = []

                    inventory[sku].append({"id": itemid, "qty": qty_disponibile})

            if page % 10 == 0 or page == total_pages:
                logging.info(
                    f"Pagina {page}/{total_pages} - {len(itemids_visti)} inserzioni"
                )

            page += 1

        except Exception as e:
            logging.error(f"Errore pagina {page}: {e}")
            break

    sku_unici = len(inventory)
    total_items = len(itemids_visti)
    sku_duplicati = sum(1 for v in inventory.values() if len(v) > 1)

    logging.info(f"✅ Inventario completo:")
    logging.info(f"   Inserzioni totali: {total_items}")
    logging.info(f"   Codici SKU unici: {sku_unici}")
    logging.info(f"   SKU con duplicati: {sku_duplicati}")

    return inventory


def update_quantities_batch(token, updates):
    """
    Aggiorna quantità su eBay in batch da 4
    updates = [{'id': ItemID, 'qty': int}, ...]
    """
    headers = {
        "X-EBAY-API-SITEID": SITE_ID,
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPATIBILITY_LEVEL,
        "X-EBAY-API-CALL-NAME": "ReviseInventoryStatus",
        "Content-Type": "text/xml",
    }

    total = len(updates)
    count_ok = 0
    count_err = 0

    logging.info(f"🚀 Aggiornamento {total} inserzioni...")

    for i in range(0, total, 4):
        batch = updates[i : i + 4]

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ReviseInventoryStatusRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
  <WarningLevel>High</WarningLevel>"""

        for item in batch:
            xml += f"""
  <InventoryStatus>
    <ItemID>{item['id']}</ItemID>
    <Quantity>{item['qty']}</Quantity>
  </InventoryStatus>"""

        xml += "\n</ReviseInventoryStatusRequest>"

        try:
            resp = requests.post(EBAY_API_URL, data=xml, headers=headers, timeout=30)

            if "<Ack>Success</Ack>" in resp.text or "<Ack>Warning</Ack>" in resp.text:
                count_ok += len(batch)
            else:
                count_err += len(batch)
                # Log dettagliato errori
                root = ET.fromstring(resp.content)
                ns = {"e": "urn:ebay:apis:eBLBaseComponents"}
                errors = root.findall(".//e:Errors", ns)
                for err in errors:
                    msg = err.find("e:ShortMessage", ns)
                    code = err.find("e:ErrorCode", ns)
                    item_ids = [item["id"] for item in batch]
                    logging.warning(
                        f"Errore batch ItemIDs={item_ids}: "
                        f"{msg.text if msg is not None else 'Unknown'} "
                        f"(Code: {code.text if code is not None else 'N/A'})"
                    )

        except Exception as e:
            count_err += len(batch)
            logging.error(f"Errore richiesta: {e}")

        time.sleep(0.25)

        processed = count_ok + count_err
        if processed > 0 and processed % 500 == 0:
            logging.info(f"📈 Progress: {processed}/{total}")

    return count_ok, count_err


def main():
    report_path = "logs/report_veloce.txt"
    start_time = datetime.now()
    logging.info("=" * 70)
    logging.info("🔄 SYNC EBAY QUANTITÀ - GESTIONE MULTI-ID CORRETTA")
    logging.info("=" * 70)

    # 1. Scarica CSV fornitore
    csv_file = download_csv()
    if not csv_file:
        return

    try:
        # 2. Leggi CSV fornitore → {SKU: qty_fornitore}
        df = pd.read_csv(csv_file, sep=";", encoding="cp1252", dtype=str)
        col_sku = next((c for c in df.columns if "articolo" in c.lower()), None)
        col_qty = next((c for c in df.columns if "giac" in c.lower()), None)

        if not col_sku or not col_qty:
            logging.error(f"Colonne non trovate: {list(df.columns)}")
            return

        csv_fornitore = {}
        for _, row in df.iterrows():
            sku = str(row[col_sku]).strip()
            qty = max(0, int(pd.to_numeric(row[col_qty], errors="coerce") or 0))
            csv_fornitore[sku] = qty

        logging.info(f"CSV fornitore: {len(csv_fornitore)} prodotti")

        # 3. Token eBay
        token = get_token()
        if not token:
            logging.error("Token non disponibile")
            return

        # 4. Scarica inventario eBay con gestione duplicati
        ebay_inventory = get_ebay_inventory_multi(token)
        if not ebay_inventory:
            logging.error("Inventario eBay vuoto")
            return

        # 5. Confronto: per ogni SKU nel fornitore, aggiorna TUTTI gli ItemID corrispondenti
        updates = []
        gia_corretti = 0
        non_su_ebay = 0

        for sku, qty_fornitore in csv_fornitore.items():
            if sku in ebay_inventory:
                # Aggiorna TUTTI gli ItemID per questo SKU (AISIN, LUK, IAP, ecc.)
                for inserzione in ebay_inventory[sku]:
                    if qty_fornitore != inserzione["qty"]:
                        updates.append({"id": inserzione["id"], "qty": qty_fornitore})
                    else:
                        gia_corretti += 1
            else:
                non_su_ebay += 1

        logging.info(
            f"📊 Già corretti: {gia_corretti} | Da aggiornare: {len(updates)} | Non su eBay: {non_su_ebay}"
        )

        if not updates:
            logging.info("✅ Tutto già sincronizzato!")
            return
        # 6. Rinnova token prima degli aggiornamenti (potrebbe essere scaduto)
        logging.info("🔄 Verifica token prima degli aggiornamenti...")
        token = get_token(silent=True)
        # 6. Aggiorna eBay
        ok, err = update_quantities_batch(token, updates)

        # 7. Riepilogo
        total_inserzioni = sum(len(v) for v in ebay_inventory.values())
        duration = (datetime.now() - start_time).total_seconds()

        logging.info("=" * 70)
        logging.info("✅ SYNC COMPLETATA")
        logging.info(f"   Durata: {duration:.1f}s ({duration/60:.1f} min)")
        logging.info(f"   Inserzioni totali eBay: {total_inserzioni}")
        logging.info(f"   Codici SKU unici: {len(ebay_inventory)}")
        logging.info(f"   Aggiornati: {ok} | Errori: {err}")
        logging.info("=" * 70)
        # --- SCRITTURA REPORT VELOCE SU FILE TESTO ---
        with open(
            report_path, "a"
        ) as f:  # "a" serve per aggiungere in fondo senza cancellare il passato
            f.write(
                f"--- SYNC DEL {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ---\n"
            )
            f.write(f"Durata: {duration/60:.1f} min\n")
            f.write(f"Inserzioni totali eBay: {total_inserzioni}\n")
            f.write(f"Codici SKU unici: {len(ebay_inventory)}\n")
            f.write(f"Prodotti Aggiornati: {ok}\n")
            f.write(f"Errori riscontrati: {err}\n")
            f.write("-" * 40 + "\n\n")

        logging.info(f"📝 Report salvato in: {report_path}")
    except Exception as e:
        logging.error(f"Errore critico: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if os.path.exists(csv_file):
            os.remove(csv_file)


if __name__ == "__main__":
    main()
