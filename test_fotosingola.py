# test_foto_singola.py
"""
Test veloce: inserisci ItemID e vedi quante foto trova GetItem
"""

from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from ebay_auth import get_token
from dotenv import load_dotenv
import os

# Setup
load_dotenv("/Users/filippocambareri/.bcc_secrets/ebay.env")

# Credenziali
EBAY_CONFIG = {
    "appid": os.environ.get("EBAY_APP_ID"),
    "certid": os.environ.get("EBAY_CERT_ID"),
    "devid": os.environ.get("EBAY_DEV_ID"),
    "domain": "api.ebay.com",
    "siteid": 101,
}

# ⚠️ INSERISCI QUI L'ITEM ID DA TESTARE
ITEM_ID = "406650067703"  # Cambia con l'ItemID che vuoi testare


def get_item_photos(api, item_id):
    """Ottiene foto di un'inserzione con GetItem"""
    try:
        response = api.execute(
            "GetItem",
            {
                "ItemID": item_id,
                "DetailLevel": "ReturnAll",
                "OutputSelector": ["ItemID", "SKU", "Title", "PictureDetails"],
            },
        )

        result = response.dict()
        item = result.get("Item", {})

        # Info inserzione
        sku = item.get("SKU", "N/A")
        title = item.get("Title", "N/A")

        # Foto
        pic_details = item.get("PictureDetails", {})
        pic_urls = pic_details.get("PictureURL", [])

        if isinstance(pic_urls, str):
            pic_urls = [pic_urls]

        return {
            "item_id": item_id,
            "sku": sku,
            "title": title,
            "foto_count": len(pic_urls),
            "foto_urls": pic_urls,
        }

    except Exception as e:
        print(f"❌ Errore: {e}")
        return None


def main():
    print("=" * 70)
    print("🧪 TEST FOTO INSERZIONE SINGOLA")
    print("=" * 70)

    # Autenticazione
    print("\n🔐 Autenticazione...")
    token = get_token()

    api = Trading(
        config_file=None,
        domain=EBAY_CONFIG["domain"],
        appid=EBAY_CONFIG["appid"],
        devid=EBAY_CONFIG["devid"],
        certid=EBAY_CONFIG["certid"],
        token=token,
        siteid=EBAY_CONFIG["siteid"],
        warnings=False,
    )

    print(f"\n📦 Test ItemID: {ITEM_ID}")
    print("─" * 70)

    # Ottieni foto
    result = get_item_photos(api, ITEM_ID)

    if result:
        print(f"\n📋 DETTAGLI INSERZIONE:")
        print(f"   ItemID: {result['item_id']}")
        print(f"   SKU: {result['sku']}")
        print(f"   Titolo: {result['title']}")

        print(f"\n📷 FOTO TROVATE: {result['foto_count']}")

        if result["foto_urls"]:
            print("\n📸 Lista foto:")
            for i, url in enumerate(result["foto_urls"], 1):
                print(f"   {i}. {url}")
        else:
            print("\n⚠️  Nessuna foto trovata!")

        print("\n" + "=" * 70)
        print(f"✅ RISULTATO: {result['foto_count']} foto presenti")
        print("=" * 70)

        if result["foto_count"] == 0:
            print("\n🚨 ATTENZIONE: 0 foto!")
            print("   Verifica su eBay se l'inserzione ha foto.")

    else:
        print("\n❌ Impossibile recuperare dati inserzione")


if __name__ == "__main__":
    main()
