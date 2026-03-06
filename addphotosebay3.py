import os
import logging
import traceback
import time
from ebaysdk.trading import Connection as Trading
from ebay_auth import get_token
from dotenv import load_dotenv

load_dotenv("/Users/filippocambareri/.bcc_secrets/ebay.env")

# ============================================================================
# CONFIGURAZIONE
# ============================================================================
START_PAGE = 1
  # Cambia per riprendere da una pagina specifica
PAGES_TO_PROCESS = None  # None = TUTTE, oppure un numero per test

PHOTO_URLS = [
    "https://i.ebayimg.com/images/g/ToIAAeSwVe5pj3PP/s-l140.webp",  # ← Le tue 6
    "https://i.ebayimg.com/images/g/hrsAAeSw-fVpj3PR/s-l140.webp",  # ← nuove
    "https://i.ebayimg.com/images/g/gbcAAeSw1kNpj3PN/s-l140.webp",
    "https://i.ebayimg.com/images/g/VJQAAeSwJZxpj3PP/s-l140.webp",  # ← giuste
    "https://i.ebayimg.com/images/g/XMgAAeSw4~9pj3PN/s-l140.webp",
    "https://i.ebayimg.com/images/g/SUYAAeSws09pj3PO/s-l140.webp",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("aggiornamento_massivo.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

error_logger = logging.getLogger("errors")
error_logger.addHandler(logging.FileHandler("errori_massivi.log"))
error_logger.setLevel(logging.ERROR)

EBAY_CONFIG = {
    "appid": os.environ.get("EBAY_APP_ID"),
    "certid": os.environ.get("EBAY_CERT_ID"),
    "devid": os.environ.get("EBAY_DEV_ID"),
    "domain": "api.ebay.com",
    "siteid": 101,
}


# ============================================================================
# FUNZIONI
# ============================================================================


def get_full_item_photos(api, item_id):
    """Ottiene l'elenco REALE di tutte le foto di un'inserzione"""
    try:
        response = api.execute(
            "GetItem",
            {
                "ItemID": item_id,
                "DetailLevel": "ReturnAll",
                "OutputSelector": [
                    "Item.PictureDetails.PictureURL",
                    "Item.SKU",
                    "Item.Title",
                ],
            },
        )
        item = response.dict().get("Item", {})
        sku = item.get("SKU", "N/A")
        title = item.get("Title", "N/A")
        pic_urls = item.get("PictureDetails", {}).get("PictureURL", [])

        if isinstance(pic_urls, str):
            pic_urls = [pic_urls]

        return pic_urls, sku, title

    except Exception as e:
        logger.error(f"      ❌ Errore GetItem per {item_id}: {e}")
        return None, None, None


def update_item_photos(api, item_id, existing_urls, new_urls, sku, title):
    """Unisce le foto e aggiorna l'inserzione"""
    try:
        urls_to_add = [u for u in new_urls if u not in existing_urls]

        if not urls_to_add:
            return "skipped_present"

        all_photos = existing_urls + urls_to_add
        all_photos = all_photos[:12]

        if len(all_photos) == len(existing_urls):
            return "skipped_full"

        api.execute(
            "ReviseFixedPriceItem",
            {"Item": {"ItemID": item_id, "PictureDetails": {"PictureURL": all_photos}}},
        )
        return "success"

    except Exception as e:
        error_logger.error(f"ID: {item_id} | SKU: {sku} | Errore: {e}")
        return "failed"


# ============================================================================
# MAIN
# ============================================================================


def main():
    logger.info("=" * 70)
    logger.info(f"🚀 PARTENZA AGGIORNAMENTO MASSIVO (Pagina iniziale: {START_PAGE})")
    logger.info("=" * 70)

    current_page = START_PAGE
    total_pages = 999
    stats = {"success": 0, "skipped": 0, "failed": 0, "total": 0}

    while current_page <= total_pages:
        # 🔑 Token fresco ad ogni pagina
        token = get_token(silent=True)
        api = Trading(
            config_file=None,
            domain=EBAY_CONFIG["domain"],
            appid=EBAY_CONFIG["appid"],
            certid=EBAY_CONFIG["certid"],
            devid=EBAY_CONFIG["devid"],
            token=token,
            siteid=EBAY_CONFIG["siteid"],
        )

        # Check limite test
        if PAGES_TO_PROCESS and (current_page >= START_PAGE + PAGES_TO_PROCESS):
            logger.info(f"\n✋ Limite pagine raggiunto ({PAGES_TO_PROCESS}). Mi fermo.")
            break

        logger.info(f"\n📄 ELABORAZIONE PAGINA {current_page}...")

        try:
            # Scarica blocco di 200 ID
            response = api.execute(
                "GetMyeBaySelling",
                {
                    "ActiveList": {
                        "Pagination": {
                            "EntriesPerPage": 200,
                            "PageNumber": current_page,
                        }
                    }
                },
            )

            res_dict = response.dict()

            # Aggiorna totale alla prima pagina
            if current_page == START_PAGE:
                pagination = res_dict["ActiveList"]["PaginationResult"]
                total_pages = int(pagination["TotalNumberOfPages"])
                total_items = int(pagination["TotalNumberOfEntries"])
                logger.info(
                    f"📊 Totale: {total_items} inserzioni su {total_pages} pagine"
                )

            items = res_dict.get("ActiveList", {}).get("ItemArray", {}).get("Item", [])
            if isinstance(items, dict):
                items = [items]

            # Processa ogni item
            for i, it in enumerate(items, 1):
                item_id = it.get("ItemID")
                stats["total"] += 1

                # Ottieni foto reali
                real_urls, sku, title = get_full_item_photos(api, item_id)

                if real_urls is None:
                    stats["failed"] += 1
                    continue

                # Aggiorna
                res = update_item_photos(
                    api, item_id, real_urls, PHOTO_URLS, sku, title
                )

                if res == "success":
                    stats["success"] += 1
                    logger.info(
                        f"   [{i}/200] ID: {item_id} | SKU: {sku} | ✅ AGGIORNATO"
                    )

                elif "skipped" in res:
                    stats["skipped"] += 1
                    logger.info(f"   [{i}/200] ID: {item_id} | SKU: {sku} | ⏭️  SALTATO")
                else:
                    stats["failed"] += 1
                    logger.error(
                        f"   [{i}/200] ID: {item_id} | SKU: {sku} | ❌ FALLITO"
                    )

            current_page += 1

        except Exception as e:
            logger.critical(f"💥 ERRORE CRITICO ALLA PAGINA {current_page}: {e}")
            error_logger.error(f"PAGINA {current_page} - ERRORE: {e}")
            break

    # Riepilogo finale
    logger.info("\n" + "=" * 70)
    logger.info("🏁 RIEPILOGO FINALE")
    logger.info(f"✅ Successi: {stats['success']}")
    logger.info(f"⏭️  Saltati:  {stats['skipped']}")
    logger.info(f"❌ Falliti:  {stats['failed']}")
    logger.info(f"📋 Totale:   {stats['total']}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
