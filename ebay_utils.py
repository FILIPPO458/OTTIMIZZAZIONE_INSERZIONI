from typing import Dict, Any, List, Optional
from ebay_description_update import build_enhanced_description

# Dizionario che mappa i tipi di prodotto alle categorie eBay
# Il formato è: "nome_categoria": ("ID_categoria", ["parole", "chiave", "italiane"])
CATEGORY_MAPPING = {
    # ASPIRAZIONE E INIEZIONE
    "ammortizzatori": ("33590", ["ammortizzat", "montant"]),
    "filtri_aria": ("33659", ["filtro aria"]),
    "filtri_carburante": (
        "33660",
        ["filtro carburante", "filtro benzina", "filtro gasolio", "filtro decantatore"],
    ),
    "filtri_olio": ("33661", ["filtro olio"]),
    "filtri_abitacolo": ("61117", ["filtro abitacolo", "filtro antipolline"]),
    # FRENI
    "dischi_freno": ("33564", ["disco freni"]),
    "pastiglie_freno": ("57357", ["pastiglie freno"]),
    "ganasce_freno": ("61739", ["ganasce freno"]),
    "pinze_freno": ("33563", ["pinze freni", "kit rev.pinze"]),
    "cilindri_freno": ("33571", ["cilindretto freni"]),
    "pompe_freno": ("33566", ["pompa freni"]),
    "tamburi_freno": ("33565", ["tamburo freni"]),
    # ILLUMINAZIONE
    "lampadine": ("172517", ["lampad", "led"]),
    "fanali_anteriori": ("33710", ["fanale anterior", "faro"]),
    "fanali_posteriori": ("33716", ["fanale posterior", "fanalino"]),
    # ACCENSIONE
    "candele": ("174072", ["candel"]),
    "candelette": ("174070", ["candeletta motore"]),
    "bobine": ("262183", ["bobina", "bobine accensione"]),
    "condensatori": ("262184", ["condensatore spinterogeno"]),
    # BATTERIE E AVVIAMENTO
    "batterie": ("179846", ["batteri", "accumulatore"]),
    "motorini_avviamento": ("177699", ["motorino avviamento"]),
    "alternatori": ("177697", ["alternatore"]),
    # TERGICRISTALLI
    "tergicristalli": ("174113", ["spazzola tergi", "tergicristall"]),
    # SOSPENSIONI E STERZO
    "tiranti_sterzo": (
        "33589",
        ["tirante assiale", "tirante scatola guida", "giunto assiale"],
    ),
    "cuffie_sterzo": ("33589", ["cuffia scatola sterzo", "cuffia sterzo"]),
    "testine_sterzo": ("33593", ["testina sterzo", "testine sterzo", "testine barra"]),
    "tiranti_assiali": ("33589", ["tirante assiale", "tirante scatola guida"]),
    "molle": ("33582", ["molla", "molle sospension"]),
    "cuscinetti_ruota": ("170141", ["cuscinetto mozzo", "mozzo ruota"]),
    "bracci_sospensione": ("33580", ["braccio sospensione"]),
    "barre_stabilizzatrici": (
        "33592",
        ["barra stabilizzatrice", "tirante barra stabilizzatrice"],
    ),
    "testine_sterzo": ("33587", ["testina sterzo"]),
    "gommini_sospensione": (
        "262229",
        ["gommino barra", "gommino braccio", "silent block"],
    ),
    "ammortizzatori_sterzo": ("262231", ["ammortizzatore sterzo"]),
    # CAMBIO E TRASMISSIONE
    "kit_frizione": ("262241", ["kit frizione", "frizione"]),
    "volano": ("33732", ["volano"]),
    "cuscinetti_frizione": ("33604", ["cuscinetto frizione"]),
    "pompe_frizione": ("262240", ["pompa frizione"]),
    "cilindri_frizione": ("262240", ["cilindretto frizione"]),
    "tubi_frizione": ("262260", ["tubo frizione"]),
    "giunti_omocinetici": ("33729", ["giunto omocinetico"]),
    "semiassi": ("262251", ["semiasse anteriore", "semiasse posteriore"]),
    "crociere": ("262252", ["crociera albero"]),
    # RAFFREDDAMENTO
    "radiatori": ("33602", ["radiatore", "vaschetta radiatore"]),
    "pompe_acqua": ("33604", ["pompa acqua"]),
    "termostati": ("33603", ["valvola termostatica", "termostat"]),
    "giunti_viscosi": ("262120", ["giunto viscoso"]),
    "radiatori_olio": ("46095", ["radiatore olio"]),
    # SCARICO
    "marmitte": ("33636", ["marmitt", "silenziator"]),
    "catalizzatori": ("33629", ["catalizzator"]),
    "sonde_lambda": ("63276", ["sonda lambda", "sensore ossigeno"]),
    # MOTORE
    "alberi_camme": ("33614", ["albero a camme", "albero camme"]),
    "alberi_motore": ("33616", ["albero motore"]),
    "bielle": ("262124", ["biella motore"]),
    "bilancieri": ("33624", ["bilanciere"]),
    "bronzine": ("33619", ["bronzine banco", "bronzine biella"]),
    "bulloni_testa": ("262129", ["bulloni testa"]),
    "carter": ("262136", ["carter distribuzione"]),
    "coperchi_punterie": ("33627", ["coperchio punterie"]),
    "guarnizioni_motore": (
        "33665",
        ["guarnizione testata", "guarnizione coppa", "guarnizioni motore"],
    ),
    "guidavalvole": ("262140", ["guidavalvola"]),
    "paraolio": ("33665", ["paraolio"]),
    "pistoni": ("33623", ["pistoni motore", "serie pistoni"]),
    "pompe_olio": ("6778", ["pompa olio"]),
    "punterie": ("61338", ["punteria idraulica"]),
    "segmenti": ("33623", ["segmenti motore"]),
    "testate": ("33617", ["testata motore"]),
    "valvole": ("33621", ["valvola aspirazione", "valvola scarico"]),
    # CINGHIE E CATENE
    "cinghie_distribuzione": ("262134", ["cinghia distribuzione"]),
    "kit_distribuzione": ("262137", ["kit distribuzione", "kit cinghia"]),
    "catene_distribuzione": ("262135", ["kit catena", "catena pompa"]),
    "cinghie_servizi": ("262060", ["cinghia servizi"]),
    "tendicinghia": (
        "33587",
        ["tendicinghia", "tenditore cinghia", "cuscinetto tendicinghia"],
    ),
    # Altri
    "generico": ("9886", []),  # categoria di fallback
}


def get_product_type(product: Dict[str, Any]) -> str:
    """
    Determina il tipo di prodotto cercando parole chiave nella descrizione.
    """
    description = product.get("description", "").lower()
    print(f"🔍 Analizzando descrizione: '{description}'")

    # Cerca in tutte le categorie
    for category_name, (category_id, keywords) in CATEGORY_MAPPING.items():
        # Salta la categoria generica
        if category_name == "generico":
            continue

        # Controlla se una delle parole chiave è presente nella descrizione
        for keyword in keywords:
            if keyword.lower() in description:
                print(
                    f"✅ Match trovato: '{keyword}' → categoria '{category_name}' (ID: {category_id})"
                )
                return category_name

    # Se non trova niente, ritorna generico
    print("⚠️ Nessun match trovato, uso categoria generica")
    return "generico"

    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    try:
        with open(path, "rb") as fh:
            resp = api.execute(
                "UploadSiteHostedPictures",
                {"PictureName": os.path.basename(path), "PictureSet": picture_set},
                files={"file": fh},
            )
    except Exception as e:
        # logga la risposta grezza se disponibile
        print("Errore upload:", e)
        if hasattr(api, "response") and api.response:
            print(api.response.dict())
        raise

    pic = resp.dict()["SiteHostedPictureDetails"]
    print("URL CDN:", pic["FullURL"])
    print("UseByDate:", pic["UseByDate"])  # utile se la foto resta in bozza
    return pic["FullURL"]


def map_basic_item(
    product: Dict[str, Any],
    custom_sku: Optional[str] = None,
    custom_brand: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ritorna il payload base.

    Args:
        product: Dati prodotto da IAP
        custom_sku: Se fornito, sovrascrive lo SKU dall'API
        custom_brand: Se fornito, sovrascrive il brand dall'API
    """
    quotation = (product.get("productQuotations") or [{}])[0]

    # Quantità
    quantity = 1
    if quotation.get("stockInformations") and len(quotation["stockInformations"]) > 0:
        stock_info = quotation["stockInformations"][0]
        if not stock_info.get("isAvailable", True):
            quantity = 0
        elif stock_info.get("isLowQuantity", False):
            quantity = 4
        else:
            quantity = 6

    images = [u for u in (product.get("image"), product.get("image2")) if u]
    attrs = {a["name"]: a["value"] for a in product.get("attributes", [])}

    product_type = get_product_type(product)
    print(f"Tipo prodotto rilevato: {product_type}")

    # PREZZO
    price_sell = quotation.get("priceSell")
    if price_sell is None:
        mpn = custom_sku or product.get(
            "manufacturerProductVariantCode", "CODICE_MANCANTE"
        )
        print(f"⚠️ SKIP: Prodotto {mpn} senza prezzo - ignorato")
        return None

    price = float((price_sell * 2) * 1.22) + 40
    print(f"  - priceSell da IAP: {price_sell}€")
    print(f"  - Prezzo finale: {price}€")

    # USA LO SKU CUSTOM SE FORNITO, ALTRIMENTI QUELLO DELL'API
    mpn = (
        custom_sku if custom_sku else product.get("manufacturerProductVariantCode", "")
    )
    print(f"Code: {mpn}")

    # USA IL BRAND CUSTOM SE FORNITO, ALTRIMENTI QUELLO DELL'API
    if custom_brand:
        brand = custom_brand
    else:
        brand = product.get("brand", "").strip()
        if brand.upper() == "QUALITY PARTS":
            brand = f"IAP {brand}"

    print(f"Brand: {brand}")

    # Titolo
    tipo = product.get("description", "")
    titolo = f"{mpn} {brand} {tipo}"
    print(f"Titolo generato: {titolo}")

    category_id = CATEGORY_MAPPING.get(product_type, ("6030", []))[0]

    # Item Specifics
    nvl = []
    nvl.append({"Name": "Marca", "Value": brand or "Generico"})

    if mpn:
        nvl.append({"Name": "MPN", "Value": mpn})

    ATTRIBUTI_DA_ESCLUDERE = ["Nota info IAP", "Nuovo prodotto", "Codice interno"]
    for name, value in attrs.items():
        if value and name not in ["Marca", "MPN"] + ATTRIBUTI_DA_ESCLUDERE:
            if name == "Tipo" and product_type == "pistoni":
                nvl.append({"Name": "Tipo", "Value": "Set di pistoni"})
            else:
                # Tronca valori troppo lunghi (max 65 caratteri per eBay)
                value_str = str(value)
                if len(value_str) > 65:
                    value_str = value_str[:62] + "..."  # Tronca a 62 + "..." = 65 caratteri
                nvl.append({"Name": name, "Value": value_str})

    nvl.append({"Name": "Garanzia produttore", "Value": "12 mesi"})
    nvl.append({"Name": "Paese di origine", "Value": "Sconosciuto"})
    if product_type == "pistoni" and not any(x["Name"] == "Tipo" for x in nvl):
        nvl.append({"Name": "Tipo", "Value": "Set di pistoni"})

    if not category_id or category_id == "":
        print(f"ATTENZIONE: Categoria non valida per {product_type}!")
        category_id = "9886"

    item = {
        "Title": titolo[:80],
        "Description": build_enhanced_description(product),
        "SKU": mpn,  # USA LO SKU PERSONALIZZATO
        "Quantity": quantity,
        "StartPrice": str(price),
        "Currency": "EUR",
        "Country": "IT",
        "Location": "Bologna",
        "PostalCode": "40012",
        "PrimaryCategory": {"CategoryID": category_id},
        "DispatchTimeMax": 3,
        "ListingDuration": "GTC",
        "ListingType": "FixedPriceItem",
        "ConditionID": 1000,
        "PictureDetails": {"PictureURL": images},
        "ItemSpecifics": {"NameValueList": nvl},
    }

    return item


def map_shipping_flat() -> Dict[str, Any]:
    """ShippingDetails con Flat rate zero cost per IT."""
    return {
        "ShippingDetails": {
            "ShippingType": "Flat",
            "ShippingServiceOptions": [
                {
                    "ShippingService": "IT_OtherCourier",
                    "ShippingServiceCost": "0.00",
                    "ShippingServiceAdditionalCost": "0.00",
                    "ShippingServicePriority": 1,
                    "ShipToLocation": "IT",
                }
            ],
        }
    }


def map_seller_profiles() -> Dict[str, Any]:
    """I profili SellerShipping/SellerReturn/SellerPayment per Trading API."""
    return {
        "SellerProfiles": {
            "SellerShippingProfile": {"ShippingProfileName": "regola di spedizione"},
            "SellerReturnProfile": {"ReturnProfileName": "regola di reso"},
            "SellerPaymentProfile": {"PaymentProfileName": "regola di pagamento"},
        }
    }
