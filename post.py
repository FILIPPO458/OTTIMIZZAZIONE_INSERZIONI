import sys
import json
import time
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from get_products_iap_funziona import get_magazzino_products
from iap_auth import get_token as get_iap_token
from get_shipping_documents_giusto import get_shipping_documents
import ebay_utils
from ebay_auth import get_token as get_ebay_token


def dump_api_response(api):
    """Stampa la risposta API per debug"""
    print("----- API RESPONSE (dict) -----")
    try:
        print(api.response.dict())
    except:
        pass


def post_fixed_price_item(config, item_data, max_retries=3):
    """Pubblica un prodotto su eBay con retry automatico"""
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
                timeout=30
            )
            
            if attempt == 1:
                print(f"📦 Payload:")
                print(json.dumps(item_data, indent=2))

            api.execute("AddFixedPriceItem", {"Item": item_data})
            dump_api_response(api)
            print(f"✅ Pubblicato")
            return True

        except ConnectionError as e:
            print(f"❌ Errore eBay (tentativo {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                print(f"⏳ Riprovo tra {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"❌ Fallito dopo {max_retries} tentativi")
                return False
                
        except Exception as e:
            print(f"❌ Errore inaspettato: {type(e).__name__} - {e}")
            return False
    
    return False


def main():
    # Config eBay (senza token hardcodato)
    config = {
        "appid": "Testuser-testuser-PRD-c933ebb76-0f37a7e0",
        "certid": "",
        "devid": "ae7da406-65bc-4091-9596-07b2c0de3cd6",
        "domain": "api.ebay.com",
        "siteid": 101,
        "debug": False,
    }
    
    # Verifica token eBay
    print("\n🔑 Verifico token eBay...")
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
    PRODOTTI = [
"702-20080",
"702-20100G",
"702-21020",
"702-21030",
"702-21040",
"702-21045",
"702-21053G",
"702-21100G",
"702-21111G",
"702-23020",
"702-25050G",
"702-28030P",
"703-00020",
"703-01010",
"703-01011",
"703-03045P",
"703-07033",
"703-07040",
"703-13041",
"703-13051",
"703-17020",
"703-17082",
"704-03042",
"704-07000P",
"704-07006",
"704-07007",
"704-07008",
"704-07105",
"704-08100",
"704-08101P",
"704-10037",
"704-10073",
"704-11152",
"704-13190P",
"704-17100",
"704-17115",
"704-17156",
"704-17198",
"704-17233",
"704-18033",
"704-20063",
"704-20090",
"704-20102",
"704-25070",
"704-25071",
"704-25080",
"704-25080P",
"704-25081",
"704-25082",
"704-27030P",
"704-28021",
"704-28021P",
"704-28033",
"704-28040",
"704-28040P",
"704-28041",
"704-50062",
"704-50063",
"704-54003",
"704-54011",
"704-54030",
"704-54040",
"704-56041",
"704-56042",
"704-56090",
"704-57014",
"705-00102",
"705-09093",
"705-10023",
"705-14031P",
"705-16058",
"705-23060",
"705-27030",
"706-03020",
"706-03040",
"706-07020",
"706-07022",
"706-07031",
"706-07050",
"706-07062",
"706-09011",
"706-12010",
"706-12031",
"706-12051",
"706-12060",
"706-14030C",
"706-14033C",
"706-14040C",
"706-16051",
"706-16080",
"706-22020",
"707-01010",
"707-01020",
"707-02011",
"707-05010",
"707-06010",
"707-06030",
"707-07030",
"707-07040",
"707-09010",
"707-10020",
"707-10040",
"707-11020",
"707-12020",
"707-13010",
"707-13041",
"707-15010",
"707-16030",
"707-16050",
"707-17020",
"708-01022",
"708-01024",
"708-02012",
"708-02013",
"708-02015",
"708-02016",
"708-02017",
"708-03015",
"708-03020",
"708-03030",
"708-03031",
"708-04050",
"708-04051",
"708-07012",
"708-07020",
"708-07022",
"708-07023",
"708-07030",
"708-07031",
"708-07050",
"708-07051",
"708-07060",
"708-07061",
"708-07090",
"708-07091",
"708-09010",
"708-09011",
"708-10013",
"708-10014",
"708-10032",
"708-10045",
"708-10049",
"708-11086",
"708-12024",
"708-12030",
"708-13011",
"708-13012",
"708-13050",
"708-13052",
"708-13060",
"708-13061",
"708-13080",
"708-13081",
"708-13091",
"708-13102",
"708-13103",
"708-14023",
"708-14024",
"708-14025",
"708-14031",
"708-14040",
"708-14050",
"708-14051",
"708-14052",
"708-16020",
"708-16080",
"708-16100",
"708-16101",
"708-17000",
"708-17001",
"708-17002",
"708-17006",
"708-17007",
"708-17008",
"708-17020",
"708-17054",
"708-17055",
"708-17056",
"708-17082",
"708-17083",
"708-17084",
"708-17085",
"708-17086",
"708-17087",
"708-17088",
"708-17089",
"708-20010",
"708-20051",
"708-20052",
"708-20060",
"708-20060G",
"708-21083",
"708-21084",
"708-21085",
"708-21086",
"708-21087",
"708-21088",
"708-22010",
"708-24022",
"708-24023",
"708-27010G",
"708-28030",
"708-28031",
"709-03044P",
"709-03045P",
"709-07006",
"709-07007",
"709-10070P",
"709-11120P",
"709-12058P",
"709-12082",
"709-13045P",
"709-13047P",
"709-13061P",
"709-13186P",
"709-13202",
"709-13226",
"709-14092",
"709-14093",
"709-15081",
"709-17108",
"709-17109",
"709-17115",
"709-17157",
"709-17158",
"709-17159",
"709-17185P",
"709-21084P",
"709-23021",
"709-23060",
"709-23060G",
"709-23061",
"709-25031",
"709-25070P",
"709-25071P",
"709-25080",
"709-25081",
"709-25082",
"709-27030P",
"709-28000",
"709-28001",
"709-28006P",
"709-28007P",
"709-28020",
"709-28021",
"709-28040",
"709-28041",
"709-50033",
"709-56041",
"709-56042",
"709-56043",
"709-57012",
"709-57014",
"710-01010",
"710-01020",
"710-01021",
"710-02010",
"710-02011",
"710-02012",
"710-02013",
"710-03020",
"710-03040",
"710-03044",
"710-03045",
"710-03097",
"710-05010",
"710-06011",
"710-07011",
"710-07020",
"710-07045G",
"710-07060",
"710-07061",
"710-07062",
"710-07064G",
"710-07065G",
"710-07067G",
"710-07080G",
"710-07090G",
"710-07094",
"710-07094G",
"710-09010",
"710-10010",
"710-10042",
"710-11071",
"710-12020",
"710-12031",
"710-12032P",
"710-12050",
"710-12060",
"710-13020",
"710-13040",
"710-13041",
"710-13042",
"710-13043",
"710-13050",
"710-13055",
"710-13060",
"710-13061",
"710-13080",
"710-13081",
"710-13082",
"710-13090",
"710-13091",
"710-13140",
"710-14020",
"710-14040",
"710-14070",
"710-16050",
"710-16051",
"710-16052",
"710-16053",
"710-16070",
"710-16076G",
"710-16083G",
"710-17000",
"710-17001",
"710-17006",
"710-17010",
"710-17056",
"710-17061",
"710-17070",
"710-17080",
"710-17090",
"710-17091",
"710-17092",
"710-18010G",
"710-18011G",
"710-18020",
"710-19010",
"710-20010",
"710-20020",
"710-20060G",
"710-20062",
"710-20070G",
"710-20080G",
"710-21020",
"710-21021",
"710-21021G",
"710-21050",
"710-21050G",
"710-21051",
"710-21051G",
"710-21052G",
"710-21070",
"710-21070G",
"710-21080",
"710-21080G",
"710-22010",
"710-22021G",
"710-22040",
"710-22040G",
"710-23040G",
"710-27030",
"710-29050",
"711-13178",
"711-28030",
"711-28031",
"802-07060",
"802-07061",
"802-07062",
"802-07063",
"802-07085G",
"802-07090",
"802-07091G",
"802-12021",
"802-12041",
"802-13090",
"802-14060",
"802-16020",
"802-16057",
"802-17083",
"802-17093",
"802-17108",
"802-17130",
"802-17150",
"802-17150G",
"802-17151",
"802-17183",
"802-17192P",
"802-18032G",
"802-20060",
"802-21021G",
"802-21051",
"802-21052",
"802-21053G",
"802-21083G",
"802-21084G",
"802-21110G",
"802-21111G",
"802-25011",
"802-25060",
"802-50030",
"802-51030",
"802-54014",
"802-57011",
"802-57012",
"803-03030G",
"803-07060",
"803-07085",
"803-07090",
"803-12020",
"803-13083",
"803-14034",
"803-16080",
"803-16080G",
"803-17010G",
"803-17040G",
"803-17050G",
"803-17120",
"803-20062",
"803-21051",
"803-21053G",
"803-21083",
"803-21084G",
"803-21110G",
"803-27030P",
"803-28020P",
"803-57011",
"809-00496",
"809-00784",
"809-01010",
"809-10040",
"809-17006P",
"809-27030P",
"809-28031P",
"810-07100P",
"814-16010",
"817-07052",
"818-10070",
"818-13140",
"818-13220",
"818-14090",
"818-14091",
"818-52090",
"818-54030",
"818-57010",
"821-04042C",
"821-04043",
"821-04043C",
"821-07097",
"821-07170",
"821-09130",
"821-09130P",
"821-10053",
"821-13112",
"821-17002",
"821-25070",
"821-25080C",
"821-28040",
"821-50041P",
"821-50061",
"821-50063C",
"821-51003C",
"821-51050C",
"821-54001CP",
"821-54010C",
"821-54010P",
"821-54011C",
"821-56060",
"821-56140C",
"822-17000",
"822-17056",
"822-17191",
"822-17240",
"840-28030",
"840-28031",
"874-14078",
"874-14079",
"874-14080",
"874-14081",
"874-14082",
"874-50020",
"874-50021",
"874-50065",
"874-50066",
"874-51006",
"874-51007",
"874-54010",
"874-57010",
"874-57011",
"874-57012",
"920-30001",
"920-30002"
  










       
       
    ]
    
    # Recupera shipping da IAP
    all_shipping = get_shipping_documents(iap_token)

    # Contatori
    totale_prodotti = 0
    pubblicati = 0
    saltati = 0
    falliti = 0

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
            totale_prodotti += 1
            prod_id = p.get("manufacturerProductVariantCode", "<UNKNOWN_ID>")
            print(f"\n▶️ [{totale_prodotti}] Processing {prod_id}")
            
            # Costruisci payload base
            item = ebay_utils.map_basic_item(p)
            
            # Se prodotto senza prezzo, salta
            if item is None:
                print(f"   ⏭️ Saltato - prodotto senza prezzo valido")
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

            # Aggiungi profili seller (CORRETTI)
            item.update(ebay_utils.map_seller_profiles())

            # Pubblica con retry
            ok = post_fixed_price_item(config, item)
            
            if ok:
                pubblicati += 1
            else:
                falliti += 1
            
            # Pausa tra pubblicazioni
            time.sleep(2)
    
    # Riepilogo finale
    print("\n" + "="*60)
    print("🎯 RIEPILOGO")
    print("="*60)
    print(f"Totale:      {totale_prodotti}")
    print(f"✅ Pubblicati: {pubblicati}")
    print(f"⏭️ Saltati:    {saltati}")
    print(f"❌ Falliti:    {falliti}")
    print("="*60)


if __name__ == "__main__":
    main()