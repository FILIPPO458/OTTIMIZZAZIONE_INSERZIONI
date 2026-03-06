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

# ========== LOGGING ==========
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


def download_from_sftp():
    """
    Scarica da SFTP:
    - CSV fornitore (più recente .csv)
    - XLSX eBay (più recente .xlsx)
    """
    result = {"csv": None, "xlsx": None}

    try:
        transport = paramiko.Transport((SFTP_CONF["host"], 22))
        transport.connect(username=SFTP_CONF["user"], password=SFTP_CONF["pass"])

        with paramiko.SFTPClient.from_transport(transport) as sftp:
            all_files = sftp.listdir_attr(SFTP_CONF["path"])

            # CSV fornitore
            csv_files = [f for f in all_files if f.filename.lower().endswith(".csv")]
            if csv_files:
                latest = max(csv_files, key=lambda x: x.st_mtime)
                sftp.get(f"{SFTP_CONF['path']}/{latest.filename}", "temp_fornitore.csv")
                result["csv"] = "temp_fornitore.csv"
                logging.info(f"CSV fornitore: {latest.filename}")

            # XLSX eBay
            xlsx_files = [f for f in all_files if f.filename.lower().endswith(".xlsx")]
            if xlsx_files:
                latest = max(xlsx_files, key=lambda x: x.st_mtime)
                sftp.get(f"{SFTP_CONF['path']}/{latest.filename}", "temp_ebay.xlsx")
                result["xlsx"] = "temp_ebay.xlsx"
                logging.info(f"XLSX eBay: {latest.filename}")

    except Exception as e:
        logging.error(f"Errore SFTP: {e}")

    return result


def load_ebay_xlsx(xlsx_file):
    """
    Legge XLSX eBay
    Ritorna: {SKU: {'itemid': str, 'qty': int}}
    """
    try:
        df = pd.read_excel(xlsx_file, dtype=str)

        # Colonne necessarie
        df["sku"] = df["Custom label (SKU)"].astype(str).str.strip()
        df["itemid"] = df["Item number"].astype(str).str.strip()
        df["qty"] = (
            pd.to_numeric(df["Available quantity"], errors="coerce")
            .fillna(0)
            .astype(int)
        )

        # Filtra righe senza SKU
        df = df[df["sku"].notna() & (df["sku"] != "nan") & (df["sku"] != "")]

        ebay_data = {}
        for _, row in df.iterrows():
            ebay_data[row["sku"]] = {"itemid": row["itemid"], "qty": row["qty"]}

        logging.info(f"✅ XLSX eBay: {len(ebay_data)} prodotti caricati")
        return ebay_data

    except Exception as e:
        logging.error(f"Errore lettura XLSX: {e}")
        return None


def load_csv_fornitore(csv_file):
    """
    Legge CSV fornitore
    Ritorna: {SKU: qty}
    """
    try:
        df = pd.read_csv(csv_file, sep=";", encoding="cp1252", dtype=str)

        col_sku = next((c for c in df.columns if "articolo" in c.lower()), None)
        col_qty = next((c for c in df.columns if "giac" in c.lower()), None)

        if not col_sku or not col_qty:
            logging.error(f"Colonne non trovate: {list(df.columns)}")
            return None

        csv_data = {}
        for _, row in df.iterrows():
            sku = str(row[col_sku]).strip()
            qty = int(pd.to_numeric(row[col_qty], errors="coerce") or 0)
            csv_data[sku] = max(0, qty)  # Mai negativi

        logging.info(f"✅ CSV fornitore: {len(csv_data)} prodotti caricati")
        return csv_data

    except Exception as e:
        logging.error(f"Errore lettura CSV: {e}")
        return None


def find_updates(ebay_data, csv_fornitore):
    """
    Confronta CSV fornitore vs XLSX eBay
    Ritorna: {ItemID: new_qty} solo per prodotti cambiati
    """
    updates = {}
    gia_corretti = 0
    non_su_ebay = 0

    for sku, new_qty in csv_fornitore.items():
        if sku in ebay_data:
            ebay_qty = ebay_data[sku]["qty"]
            itemid = ebay_data[sku]["itemid"]

            if new_qty != ebay_qty:
                # Quantità diversa → aggiorna!
                updates[itemid] = new_qty
            else:
                gia_corretti += 1
        else:
            # Prodotto non pubblicato su eBay → skip
            non_su_ebay += 1

    logging.info(
        f"📊 Già corretti: {gia_corretti} | Da aggiornare: {len(updates)} | Non su eBay: {non_su_ebay}"
    )
    return updates


def update_quantities_batch(token, updates):
    """
    Aggiorna quantità eBay in batch da 4 usando ItemID
    updates = {ItemID: qty}
    """
    headers = {
        "X-EBAY-API-SITEID": SITE_ID,
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPATIBILITY_LEVEL,
        "X-EBAY-API-CALL-NAME": "ReviseInventoryStatus",
        "Content-Type": "text/xml",
    }

    items_list = list(updates.items())
    total = len(items_list)
    count_ok = 0
    count_err = 0

    logging.info(f"🚀 Aggiornamento {total} prodotti (batch da 4)...")

    for i in range(0, total, 4):
        batch = items_list[i : i + 4]

        # XML con ItemID
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ReviseInventoryStatusRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
  <WarningLevel>High</WarningLevel>"""

        for itemid, qty in batch:
            xml += f"""
  <InventoryStatus>
    <ItemID>{itemid}</ItemID>
    <Quantity>{qty}</Quantity>
  </InventoryStatus>"""

        xml += "\n</ReviseInventoryStatusRequest>"

        try:
            resp = requests.post(EBAY_API_URL, data=xml, headers=headers, timeout=30)

            if "<Ack>Success</Ack>" in resp.text or "<Ack>Warning</Ack>" in resp.text:
                count_ok += len(batch)
            else:
                count_err += len(batch)
                logging.warning(f"Errore batch: {resp.text[:200]}")

        except Exception as e:
            count_err += len(batch)
            logging.error(f"Errore chiamata: {e}")

        time.sleep(0.25)  # Rate limiting

        # Progress ogni 500
        processed = count_ok + count_err
        if processed > 0 and processed % 500 == 0:
            logging.info(f"📈 Progress: {processed}/{total}")

    return count_ok, count_err


def main():
    start_time = datetime.now()
    logging.info("=" * 70)
    logging.info("🔄 SYNC EBAY QUANTITÀ - XLSX + CSV FORNITORE")
    logging.info("=" * 70)

    # 1. Scarica file da SFTP
    files = download_from_sftp()

    if not files["csv"]:
        logging.error("❌ CSV fornitore non trovato su SFTP")
        return

    if not files["xlsx"]:
        logging.error("❌ XLSX eBay non trovato su SFTP")
        logging.error("   Carica il file Excel eBay nella porta SFTP!")
        return

    try:
        # 2. Carica XLSX eBay (ItemID + SKU + Qty)
        ebay_data = load_ebay_xlsx(files["xlsx"])
        if not ebay_data:
            return

        # 3. Carica CSV fornitore (SKU + Giacenza)
        csv_fornitore = load_csv_fornitore(files["csv"])
        if not csv_fornitore:
            return

        # 4. Trova differenze (confronto diretto!)
        updates = find_updates(ebay_data, csv_fornitore)

        if not updates:
            logging.info("✅ Tutte le quantità sono già corrette!")
            return

        # 5. Token eBay
        token = get_token()
        if not token:
            logging.error("❌ Token eBay non disponibile")
            return

        # 6. Aggiorna eBay con ItemID
        ok, err = update_quantities_batch(token, updates)

        # 7. Riepilogo
        duration = (datetime.now() - start_time).total_seconds()
        logging.info("=" * 70)
        logging.info("✅ SYNC COMPLETATA")
        logging.info(f"   Durata: {duration:.1f}s ({duration/60:.1f} min)")
        logging.info(f"   Prodotti eBay nel file: {len(ebay_data)}")
        logging.info(f"   Aggiornati: {ok} | Errori: {err}")
        logging.info("=" * 70)

    except Exception as e:
        logging.error(f"❌ Errore critico: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Pulizia file temporanei
        for f in ["temp_fornitore.csv", "temp_ebay.xlsx"]:
            if os.path.exists(f):
                os.remove(f)
                logging.info(f"File temporaneo rimosso: {f}")


if __name__ == "__main__":
    main()
