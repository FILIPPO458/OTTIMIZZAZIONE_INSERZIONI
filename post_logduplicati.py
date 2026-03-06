import sys
import json
import time
from datetime import datetime
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from get_products_iap_funziona import get_magazzino_products
from iap_auth import get_token as get_iap_token
from get_shipping_documents_giusto import get_shipping_documents
import ebay_utils
from ebay_auth import get_token as get_ebay_token


LOG_FILE = "pubblicati.json"


def load_log():
    """Carica il log dei prodotti già pubblicati"""
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"pubblicati": [], "falliti": [], "saltati": [], "last_update": None}
    except json.JSONDecodeError:
        print("⚠️ Log corrotto, ricreo file vuoto")
        return {"pubblicati": [], "falliti": [], "saltati": [], "last_update": None}


def save_log(log_data):
    """Salva il log aggiornato"""
    log_data["last_update"] = datetime.now().isoformat()
    with open(LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=2)


def add_to_log(log_data, sku, status):
    """Aggiunge un prodotto al log con stato (pubblicato/fallito/saltato)"""
    if status == "pubblicato" and sku not in log_data["pubblicati"]:
        log_data["pubblicati"].append(sku)
    elif status == "fallito" and sku not in log_data["falliti"]:
        log_data["falliti"].append(sku)
    elif status == "saltato" and sku not in log_data["saltati"]:
        log_data["saltati"].append(sku)
    save_log(log_data)


def dump_api_response(api):
    """Stampa la risposta API per debug"""
    print("----- API RESPONSE (dict) -----")
    try:
        print(api.response.dict())
    except:
        pass


def post_fixed_price_item(config, item_data, sku, log_data, max_retries=3):
    """Pubblica un prodotto su eBay con retry automatico e gestione duplicati"""
    # Rimuovi ShippingDetails per evitare conflitti
    item_data.pop("ShippingDetails", None)

    for attempt in range(1, max_retries + 1):
        try:
            # Ottieni token fresco ad ogni tentativo
            fresh_token = get_ebay_token(silent=(attempt > 1))

            api = Trading(
                config_file=None,
                domain=config["domain"],
                appid=config["appid"],
                devid=config["devid"],
                certid=config["certid"],
                token=fresh_token,
                siteid=config["siteid"],
                warnings=False,
                debug=config["debug"],
                timeout=30,
            )

            if attempt == 1:
                print(f"📦 Payload:")
                print(json.dumps(item_data, indent=2))

            api.execute("AddFixedPriceItem", {"Item": item_data})
            dump_api_response(api)
            print(f"✅ Pubblicato")
            add_to_log(log_data, sku, "pubblicato")
            return True

        except ConnectionError as e:
            error_msg = str(e)

            # Se è duplicato, segna come già pubblicato
            if (
                "duplicate" in error_msg.lower()
                or "already exists" in error_msg.lower()
            ):
                print(f"⚠️ Prodotto già esistente su eBay")
                add_to_log(log_data, sku, "pubblicato")
                return True

            print(f"❌ Errore eBay (tentativo {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait_time = 2**attempt
                print(f"⏳ Riprovo tra {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"❌ Fallito dopo {max_retries} tentativi")
                add_to_log(log_data, sku, "fallito")
                return False

        except Exception as e:
            print(f"❌ Errore inaspettato: {type(e).__name__} - {e}")
            add_to_log(log_data, sku, "fallito")
            return False

    return False


def main():
    # Config eBay
    config = {
        "appid": "Testuser-testuser-PRD-c933ebb76-0f37a7e0",
        "certid": "",
        "devid": "ae7da406-65bc-4091-9596-07b2c0de3cd6",
        "domain": "api.ebay.com",
        "siteid": 101,
        "debug": False,
    }

    # Carica log
    log_data = load_log()

    print("\n" + "=" * 60)
    print("📊 STATO ATTUALE")
    print("=" * 60)
    print(f"✅ Già pubblicati: {len(log_data['pubblicati'])}")
    print(f"❌ Falliti:        {len(log_data['falliti'])}")
    print(f"⏭️ Saltati:        {len(log_data['saltati'])}")
    if log_data["last_update"]:
        print(f"🕒 Ultimo update:  {log_data['last_update']}")
    print("=" * 60 + "\n")

    # Verifica token eBay
    print("🔑 Verifico token eBay...")
    try:
        ebay_token = get_ebay_token()
        print(f"✅ Token eBay valido: {ebay_token[:50]}...\n")
    except Exception as e:
        print(f"❌ Errore token eBay: {e}")
        print("⚠️ Esegui prima ebay_auth.py per ottenere un token valido")
        return

    # Token IAP
    iap_token = get_iap_token()

    # Lista prodotti completa
    PRODOTTI = []

    # Recupera shipping da IAP
    all_shipping = get_shipping_documents(iap_token)

    # Contatori
    totale_processati = 0
    pubblicati = 0
    saltati = 0
    falliti = 0
    gia_pubblicati = 0

    # Loop sui codici prodotto
    for codice in PRODOTTI:
        resp = get_magazzino_products(iap_token, search_term=codice)
        batches = resp.get("data", [])

        if not batches:
            print(f"⚠️ Nessun batch per {codice}")
            continue

        products = batches[0].get("data", [])
        if not products:
            print(f"⚠️ Nessun prodotto per {codice}")
            continue

        # Loop sui prodotti del batch
        for p in products:
            prod_id = p.get("manufacturerProductVariantCode", "<UNKNOWN_ID>")

            # Controlla se già pubblicato
            if prod_id in log_data["pubblicati"]:
                gia_pubblicati += 1
                print(f"\n✓ [{gia_pubblicati}] {prod_id} - GIÀ PUBBLICATO (skip)")
                continue

            totale_processati += 1
            print(f"\n▶️ [{totale_processati}] Processing {prod_id}")

            # Costruisci payload base
            item = ebay_utils.map_basic_item(p)

            # Se prodotto senza prezzo, salta
            if item is None:
                print(f"   ⏭️ Saltato - prodotto senza prezzo valido")
                add_to_log(log_data, prod_id, "saltato")
                saltati += 1
                continue

            # Aggiungi shipping flat
            item.update(ebay_utils.map_shipping_flat())

            # Sovrascrivi con shipping IAP se disponibile
            shipping_iap = next(
                (s for s in all_shipping if s.get("product_id") == prod_id), {}
            )
            if shipping_iap:
                item.update(shipping_iap)

            # Aggiungi profili seller
            item.update(ebay_utils.map_seller_profiles())

            # Pubblica con retry e log automatico
            ok = post_fixed_price_item(config, item, prod_id, log_data)

            if ok:
                pubblicati += 1
            else:
                falliti += 1

            # Pausa tra pubblicazioni
            time.sleep(2)

    # Riepilogo finale
    print("\n" + "=" * 60)
    print("🎯 RIEPILOGO FINALE")
    print("=" * 60)
    print(f"Processati ora:   {totale_processati}")
    print(f"✅ Pubblicati ora: {pubblicati}")
    print(f"⏭️ Saltati ora:    {saltati}")
    print(f"❌ Falliti ora:    {falliti}")
    print(f"✓ Già pubblicati: {gia_pubblicati}")
    print("-" * 60)
    print(f"TOTALE pubblicati: {len(log_data['pubblicati'])}")
    print(f"TOTALE falliti:    {len(log_data['falliti'])}")
    print(f"TOTALE saltati:    {len(log_data['saltati'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
