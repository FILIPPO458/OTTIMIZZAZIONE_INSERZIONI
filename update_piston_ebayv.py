# update_piston_ebay.py
import json
import logging
import os
from dotenv import load_dotenv
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from get_products_iap_funziona import get_magazzino_products
from datetime import datetime  # <--- AGGIUNGI QUESTO IN CIMA AL FILE

# 🆕 IMPORT MODULI AUTH
from iap_auth import get_token as get_iap_token
from ebay_auth import get_token as get_ebay_token

from extract_piston_specsv import get_piston_specs, map_to_ebay_specifics

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("update_pistons_ebay.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)
load_dotenv('/Users/filippocambareri/.bcc_secrets/ebay.env')
# Config eBay (senza token hardcoded)
EBAY_CONFIG = {
    "appid": os.environ.get("EBAY_APP_ID"),
    "certid": os.environ.get("EBAY_CERT_ID"),
    "devid": os.environ.get("EBAY_DEV_ID"),
    "domain": "api.ebay.com",
    "siteid": 101,
    "debug": False,
}

# 👇 INCOLLA QUI I CODICI PISTONI
PISTONI_SKU = ["100-00116"]


# ============================================================================
# FUNZIONE: SCARICA TUTTO EBAY UNA VOLTA
# ============================================================================


def download_all_ebay_listings(api):
    """
    Scarica TUTTE le inserzioni attive da eBay
    Returns: dict {SKU: {'item_id': ..., 'title': ...}}
    """
    logger.info("\n" + "=" * 70)
    logger.info("📥 DOWNLOAD TUTTE LE INSERZIONI EBAY...")

    sku_map = {}
    page = 1
    total_pages = 1

    while page <= total_pages:
        try:
            logger.info(f"   📄 Pagina {page}/{total_pages}...")

            response = api.execute(
                "GetMyeBaySelling",
                {
                    "ActiveList": {
                        "Include": True,
                        "Pagination": {"EntriesPerPage": 200, "PageNumber": page},
                    },
                    "OutputSelector": ["ItemID", "SKU", "Title", "PaginationResult"],
                },
            )

            result = response.dict()
            active_list = result.get("ActiveList", {})

            if page == 1:
                pagination = active_list.get("PaginationResult", {})
                total_pages = int(pagination.get("TotalNumberOfPages", 1))
                total_entries = int(pagination.get("TotalNumberOfEntries", 0))
                logger.info(
                    f"   📊 Totale: {total_entries} inserzioni in {total_pages} pagine"
                )

            items = active_list.get("ItemArray", {}).get("Item", [])

            # Se singolo item, eBay restituisce dict invece di lista
            if isinstance(items, dict):
                items = [items]

            for item in items:
                sku = item.get("SKU")
                if sku:
                    sku_map[sku] = {
                        "item_id": item.get("ItemID"),
                        "title": item.get("Title", "N/A"),
                    }

            page += 1

        except ConnectionError as e:
            logger.error(f"   ❌ Errore pagina {page}: {e}")
            break

    logger.info(f"   ✅ Download completato: {len(sku_map)} SKU in memoria")
    logger.info("=" * 70 + "\n")

    return sku_map


# ============================================================================
# FUNZIONI EBAY
# ============================================================================


def find_item_in_memory(sku, sku_map):
    """Cerca ItemID in memoria (istantaneo)"""
    if sku in sku_map:
        item_id = sku_map[sku]["item_id"]
        title = sku_map[sku]["title"]
        logger.info(f"   ✅ Trovato: {item_id} - {title[:50]}")
        return item_id
    else:
        logger.warning(f"   ⚠️ SKU {sku} non trovato su eBay")
        return None


def update_ebay_item(api, item_id, item_specifics):
    """Aggiorna ItemSpecifics con ReviseFixedPriceItem"""
    try:
        payload = {
            "Item": {
                "ItemID": item_id,
                "ItemSpecifics": item_specifics["ItemSpecifics"],
            }
        }

        logger.info(f"   📤 Aggiorno ItemID {item_id}...")
        api.execute("ReviseFixedPriceItem", payload)

        logger.info(f"   ✅ Aggiornato")
        return True

    except ConnectionError as e:
        logger.error(f"   ❌ Errore: {e}")
        return False


# ============================================================================
# LOGICA PRINCIPALE
# ============================================================================


def update_piston(sku, iap_token, api, sku_map):
    """
    Aggiorna un pistone
    1. Cerca in memoria (istantaneo)
    2. Recupera da IAP
    3. Estrae specs
    4. Aggiorna eBay
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"🔧 PISTONE: {sku}")

    # STEP 1: Cerca in memoria
    item_id = find_item_in_memory(sku, sku_map)
    if not item_id:
        return False

    # STEP 2: Recupera da IAP
    logger.info(f"   📡 IAP...")
    try:
        resp = get_magazzino_products(iap_token, search_term=sku)
        batches = resp.get("data", [])

        if not batches or not batches[0].get("data"):
            logger.error(f"   ❌ Nessun dato IAP")
            return False

        product = batches[0]["data"][0]

    except Exception as e:
        logger.error(f"   ❌ Errore IAP: {e}")
        return False

    # STEP 3: Estrai specs
    specs = get_piston_specs(product)
    if not specs:
        logger.warning(f"   ⚠️ Nessuna spec")
        return False

    ebay_specifics = map_to_ebay_specifics(specs, product)
    if not ebay_specifics:
        logger.warning(f"   ⚠️ Mapping fallito")
        return False

    logger.info(f"   📊 {len(ebay_specifics['ItemSpecifics']['NameValueList'])} campi")

    # STEP 4: Aggiorna eBay
    return update_ebay_item(api, item_id, ebay_specifics)


def main():
    """Entry point"""
    logger.info("=" * 70)
    logger.info("🚀 AGGIORNAMENTO PISTONI SU EBAY")
    logger.info(f"📋 Pistoni: {len(PISTONI_SKU)}")
    logger.info("=" * 70)

    # 🆕 OTTIENI TOKEN DINAMICAMENTE
    logger.info("\n🔐 Autenticazione...")
    iap_token = get_iap_token()
    ebay_token = get_ebay_token()

    # Crea oggetto Trading con token dinamico
    api = Trading(
        config_file=None,
        domain=EBAY_CONFIG["domain"],
        appid=EBAY_CONFIG["appid"],
        devid=EBAY_CONFIG["devid"],
        certid=EBAY_CONFIG["certid"],
        token=ebay_token,  # 🆕 Token dinamico
        siteid=EBAY_CONFIG["siteid"],
        warnings=False,
        debug=EBAY_CONFIG["debug"],
    )

    # Download tutto eBay una volta
    sku_map = download_all_ebay_listings(api)

    # Contatori
    success = 0
    failed = 0
    # 🆕 Lista per salvare codici falliti
    failed_skus_list = []
    # Loop pistoni
    for sku in PISTONI_SKU:
        try:
            result = update_piston(sku, iap_token, api, sku_map)
            if result:
                success += 1
            else:
                failed += 1
                failed_skus_list.append(sku)
        except Exception as e:
            logger.error(f"❌ Errore: {e}")
            failed += 1
            failed_skus_list.append(sku)

    # Riepilogo
    logger.info("\n" + "=" * 70)
    logger.info("📊 RIEPILOGO")
    logger.info(f"✅ Aggiornati: {success}")
    logger.info(f"❌ Falliti: {failed}")
    logger.info(f"📋 Totale: {len(PISTONI_SKU)}")
    logger.info("=" * 70)

    if failed_skus_list:
        filename = "pistoni_falliti.txt"
        try:
            with open(filename, "a") as f:
                for sku_fail in failed_skus_list:
                    f.write(f"{sku_fail}\n")

            logger.info("-" * 70)
            logger.info(f"💾 Codici falliti salvati in: {filename}")
            logger.info("   Puoi copiarli per un secondo tentativo.")
        except Exception as e:
            logger.error(f"⚠️ Errore salvataggio file: {e}")


if __name__ == "__main__":
    main()
