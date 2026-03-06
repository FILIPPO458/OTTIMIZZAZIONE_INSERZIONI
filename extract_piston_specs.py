# extract_piston_specs.py
import json
import requests
import base64
import re
import os
import logging
import time
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

# ============================================================================
# CONFIGURAZIONE
# ============================================================================
load_dotenv("/Users/filippocambareri/.bcc_secrets/ebay.env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CACHE_FILE = "piston_specs_cache.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("piston_extraction.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Mapping IAP Attributes (italiano)
IAP_ATTRIBUTES_MAP = {
    211810: "diametro_pistone",  # Diametro pistone [mm]
    210724: "diametro_spinotto",  # Bullone-Ø [mm]
    211177: "altezza_compressione",  # Altezza di compressione [mm]
    211168: "spessore_fascia_1",  # Spessore 1 [mm]
    211169: "spessore_fascia_2",  # Spessore 2 [mm]
    210124: "spessore_fascia_olio",  # Spessore [mm] (la terza fascia)
    210203: "lunghezza_totale",  # Lunghezza [mm]
    210596: "info_integrativa",  # Articolo complementare/Info integrativa
    210219: "materiale",  # Materiale
    213217: "numero_pezzi",  # Numero pezzi [pz.] - solitamente 4
}

# Mapping Claude Vision (inglese → italiano)
CLAUDE_TO_IAP_MAP = {
    "bore_diameter": "diametro_pistone",
    "pin_diameter": "diametro_spinotto",
    "pin_length": "lunghezza_spinotto",
    "compression_height": "altezza_compressione",
    "compression_height_dome": "altezza_cupola",  # +3.4 (Dome)
    "compression_height_dish": "profondita_incavo",  # -2.3 (Dish)
    "length": "lunghezza_totale",
    "ring_top": "spessore_fascia_1",
    "ring_second": "spessore_fascia_2",
    "ring_oil": "spessore_fascia_olio",
    "material": "materiale",
}

REQUIRED_FIELDS = ["diametro_pistone", "diametro_spinotto"]

# ============================================================================
# CACHE MANAGEMENT
# ============================================================================


def load_cache():
    if Path(CACHE_FILE).exists():
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


_cache = load_cache()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def clean_numeric_value(value):
    """
    Pulisce valori numerici da testo extra
    "84 mm" → "84"
    "circa 84.5" → "84.5"
    "2,5" → "2.5"
    """
    if not value:
        return None
    match = re.search(r"[0-9]+[.,]?[0-9]*", str(value))
    if match:
        cleaned = match.group(0).replace(",", ".")
        return cleaned
    return None


def is_serie_100(mpn):
    """Verifica se è Serie 100 (completa con fasce)"""
    return mpn.startswith("100-")


def is_serie_101(mpn):
    """Verifica se è Serie 101 (senza fasce)"""
    return mpn.startswith("101-")


# ============================================================================
# STEP 1: ESTRAZIONE DA IAP
# ============================================================================


def extract_iap_attributes(product):
    """Estrae attributes da IAP con pulizia valori"""
    specs = {}
    attributes = product.get("attributes", [])

    for attr in attributes:
        attr_id = attr.get("attributeId")
        if attr_id in IAP_ATTRIBUTES_MAP:
            field_name = IAP_ATTRIBUTES_MAP[attr_id]
            val = attr.get("value", "").strip()

            # Pulizia valore numerico
            if field_name not in ["info_integrativa", "materiale"]:
                val = clean_numeric_value(val)

            if val:
                specs[field_name] = val

    return specs


def is_complete(specs):
    """Verifica completezza dati"""
    for field in REQUIRED_FIELDS:
        if field not in specs or not specs[field]:
            return False
    return True


# ============================================================================
# STEP 2: DOWNLOAD IMMAGINE
# ============================================================================


def download_image(image_url, max_retries=3):
    """
    Scarica immagine con retry automatico
    Returns: (base64_data, media_type) o (None, None)
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(image_url, timeout=15)

            if response.status_code == 200:
                media_type = response.headers.get("Content-Type", "image/jpeg")

                if not media_type.startswith("image/"):
                    if image_url.lower().endswith(".png"):
                        media_type = "image/png"
                    elif image_url.lower().endswith(".webp"):
                        media_type = "image/webp"
                    else:
                        media_type = "image/jpeg"

                img_b64 = base64.b64encode(response.content).decode("utf-8")
                return img_b64, media_type

            elif response.status_code == 404:
                logger.error(f"Immagine non trovata (404): {image_url}")
                return None, None

            elif response.status_code == 403:
                logger.error(f"Accesso negato (403): {image_url}")
                return None, None

            else:
                logger.warning(
                    f"Status {response.status_code}, retry {attempt+1}/{max_retries}"
                )
                time.sleep(2**attempt)

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout download, retry {attempt+1}/{max_retries}")
            time.sleep(2**attempt)

        except requests.exceptions.RequestException as e:
            logger.error(f"Errore download: {e}")
            if attempt == max_retries - 1:
                return None, None
            time.sleep(2**attempt)

    return None, None


# ============================================================================
# STEP 3: CLAUDE VISION
# ============================================================================


def extract_with_claude(image_url, mpn, max_retries=3):
    """
    Estrae dati con Claude Vision API
    Usa cache per evitare chiamate duplicate
    """
    cache_key = f"{mpn}_{image_url}"
    if cache_key in _cache:
        logger.info(f"   💾 Cache hit - skip API")
        return _cache[cache_key]

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY non configurata!")
        return {}

    logger.info("   🔍 Download immagine...")
    img_data, media_type = download_image(image_url)

    if not img_data:
        return {}

    logger.info("   🤖 Claude Vision API...")
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = """Analyze this technical drawing of a piston.

INSTRUCTIONS:
- Extract ONLY numeric values in millimeters
- For bore diameter: take the main value
- For compression height: take the nominal value AND the tolerances
  * If you see +3.4 or similar → "compression_height_dome": "3.4"
  * If you see -2.3 or similar → "compression_height_dish": "2.3"
  * These are the dome height (bombatura) and dish depth (incavo)
- For rings: TOP, 2nd, Oil in this order
- If a value is not clearly readable, use null

Respond ONLY with valid JSON (NO markdown, NO text):
{
  "bore_diameter": "value",
  "pin_diameter": "value",
  "pin_length": "value",
  "compression_height": "value",
  "compression_height_dome": "value or null",
  "compression_height_dish": "value or null",
  "length": "value",
  "ring_top": "value",
  "ring_second": "value",
  "ring_oil": "value",
  "material": "material description if visible"
}"""

    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": img_data,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            response_text = message.content[0].text.strip()
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

            specs_claude = json.loads(response_text)

            # Pulizia valori numerici
            for key in specs_claude.keys():
                if key in [
                    "bore_diameter",
                    "pin_diameter",
                    "pin_length",
                    "compression_height",
                    "length",
                    "ring_top",
                    "ring_second",
                    "ring_oil",
                ]:
                    if specs_claude[key]:
                        specs_claude[key] = clean_numeric_value(specs_claude[key])

            # Converti nomi campi inglese → italiano
            specs_italian = {}
            for eng_key, ita_key in CLAUDE_TO_IAP_MAP.items():
                if eng_key in specs_claude and specs_claude[eng_key]:
                    specs_italian[ita_key] = specs_claude[eng_key]

            # Salva in cache
            _cache[cache_key] = specs_italian
            save_cache(_cache)

            logger.info("   ✅ Dati estratti")
            return specs_italian

        except json.JSONDecodeError as e:
            logger.error(f"   ❌ JSON parsing error: {e}")
            logger.debug(f"   Response: {response_text}")
            return {}

        except Exception as e:
            logger.warning(
                f"   ⚠️ Claude API error, retry {attempt+1}/{max_retries}: {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
            else:
                logger.error(f"   ❌ Max retries raggiunto")
                return {}

    return {}


# ============================================================================
# STEP 4: LOGICA IBRIDA
# ============================================================================


def get_piston_specs(product):
    """
    Strategia ibrida:
    1. IAP attributes
    2. Claude Vision se incompleto
    3. Merge con priorità IAP
    """
    mpn = product.get("manufacturerProductVariantCode", "UNKNOWN")
    logger.info(f"\n{'='*60}")
    logger.info(f"▶️ Elaboro pistone: {mpn}")

    # Step 1: IAP
    specs_iap = extract_iap_attributes(product)
    logger.info(f"   📋 IAP attributes: {len(specs_iap)} campi")

    if is_complete(specs_iap):
        logger.info(f"   ✅ Dati IAP completi - skip AI (€0.00)")
        return specs_iap

    # Step 2: Claude Vision
    logger.info(f"   ⚠️ Dati IAP incompleti - attivo AI (~€0.003)")
    image_url = product.get("image")

    if not image_url:
        logger.warning(f"   ❌ Nessuna immagine disponibile")
        return specs_iap

    specs_claude = extract_with_claude(image_url, mpn)

    # Step 3: Merge (priorità IAP)
    specs_final = {**specs_claude, **specs_iap}

    logger.info(f"   📊 Specs finali: {len(specs_final)} campi")
    return specs_final


# ============================================================================
# STEP 5: MAPPING EBAY
# ============================================================================


def map_to_ebay_specifics(specs, product):
    """Converte specs in eBay ItemSpecifics"""
    if not specs:
        return None

    mpn = product.get("manufacturerProductVariantCode", "")

    nvl = [
        {"Name": "Marca", "Value": "IAP QUALITY PARTS"},
        {"Name": "MPN", "Value": mpn},
        {"Name": "Tipo", "Value": "Set di pistoni"},
    ]

    # Materiale (default se non presente)
    material = specs.get("materiale", "Lega di alluminio")
    if len(material) > 65:
        material = material[:62] + "..."
    nvl.append({"Name": "Materiale", "Value": material})

    # Articoli inclusi - LOGICA SERIE 100 vs 101
    if is_serie_100(mpn):
        # Serie 100: SET COMPLETO
        nvl.append(
            {
                "Name": "Articoli inclusi",
                "Value": ["Pistone", "Anelli per pistone", "Spinotto", "Fermo"],
            }
        )
    elif is_serie_101(mpn):
        # Serie 101: SENZA FASCE
        nvl.append(
            {"Name": "Articoli inclusi", "Value": ["Pistone", "Spinotto", "Fermo"]}
        )
    # Numero di pistoni nel kit (solitamente 4)
    if specs.get("numero_pezzi"):
        nvl.append(
            {"Name": "Numero di pistoni nel kit", "Value": specs["numero_pezzi"]}
        )

    # Diametri principali
    if specs.get("diametro_pistone"):
        nvl.append(
            {"Name": "Diametro del pistone", "Value": f"{specs['diametro_pistone']} mm"}
        )
        nvl.append(
            {
                "Name": "Diametro del foro del cilindro",
                "Value": f"{specs['diametro_pistone']} mm",
            }
        )

    if specs.get("diametro_spinotto"):
        nvl.append(
            {
                "Name": "Diametro dello spinotto",
                "Value": f"{specs['diametro_spinotto']} mm",
            }
        )

    # Spessore = Spessore fasce (TOP/2nd/Oil) - SOLO per Serie 100
    if is_serie_100(mpn):
        ring_vals = []
        if specs.get("spessore_fascia_1"):
            ring_vals.append(specs["spessore_fascia_1"])
        if specs.get("spessore_fascia_2"):
            ring_vals.append(specs["spessore_fascia_2"])
        if specs.get("spessore_fascia_olio"):
            ring_vals.append(specs["spessore_fascia_olio"])

        if ring_vals:
            nvl.append({"Name": "Spessore", "Value": f"{'/'.join(ring_vals)} mm"})

    # Serie 101: campo Spessore vuoto o con valore generico
    # (eBay potrebbe richiederlo, ma non abbiamo fasce per Serie 101)

    # Peso standard per set pistoni
    nvl.append({"Name": "Peso", "Value": "2 kg"})

    # Campi tecnici separati (NON concatenati)
    if specs.get("altezza_compressione"):
        nvl.append(
            {
                "Name": "Altezza compressione",
                "Value": f"{specs['altezza_compressione']} mm",
            }
        )

    if specs.get("lunghezza_totale"):
        nvl.append({"Name": "Lunghezza", "Value": f"{specs['lunghezza_totale']} mm"})

    if specs.get("lunghezza_spinotto"):
        nvl.append(
            {"Name": "Lunghezza spinotto", "Value": f"{specs['lunghezza_spinotto']} mm"}
        )

    # Tolleranze compression height (Dome e Dish) - Specifiche personalizzate
    if specs.get("altezza_cupola"):
        nvl.append(
            {"Name": "Altezza cupola (Dome)", "Value": f"+{specs['altezza_cupola']} mm"}
        )

    if specs.get("profondita_incavo"):
        nvl.append(
            {
                "Name": "Profondità incavo (Dish)",
                "Value": f"-{specs['profondita_incavo']} mm",
            }
        )

    # Spessore fasce SOLO per Serie 100 (campo separato)
    if is_serie_100(mpn):
        ring_vals = []
        if specs.get("spessore_fascia_1"):
            ring_vals.append(specs["spessore_fascia_1"])
        if specs.get("spessore_fascia_2"):
            ring_vals.append(specs["spessore_fascia_2"])
        if specs.get("spessore_fascia_olio"):
            ring_vals.append(specs["spessore_fascia_olio"])

        if ring_vals:
            nvl.append({"Name": "Spessore fasce", "Value": f"{'/'.join(ring_vals)} mm"})

    # Info integrativa da IAP (se presente, come campo finale)
    if specs.get("info_integrativa"):
        nvl.append(
            {
                "Name": "Articolo complementare/Info integrativa",
                "Value": specs["info_integrativa"],
            }
        )

    return {"ItemSpecifics": {"NameValueList": nvl}}


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test Serie 100 (completo)
    test_100 = {
        "manufacturerProductVariantCode": "100-00114",
        "image": "https://www.iapqualityparts.com/img-server/productmasters/details/100-00114.jpg",
        "attributes": [
            {"attributeId": 211810, "value": "72.25"},
            {"attributeId": 210724, "value": "18"},
        ],
    }

    # Test Serie 101 (senza segmenti)
    test_101 = {
        "manufacturerProductVariantCode": "101-17041",
        "image": "https://www.iapqualityparts.com/img-server/productmasters/details/101-17041.jpg",
        "attributes": [
            {"attributeId": 211810, "value": "91.50"},
            {"attributeId": 210724, "value": "29"},
        ],
    }

    print("\n" + "=" * 70)
    print("TEST SERIE 100 (completo con fasce)")
    print("=" * 70)
    specs_100 = get_piston_specs(test_100)
    print(f"\n📊 Specs estratte:")
    print(json.dumps(specs_100, indent=2, ensure_ascii=False))

    ebay_100 = map_to_ebay_specifics(specs_100, test_100)
    print(f"\n🏷️ eBay ItemSpecifics:")
    print(json.dumps(ebay_100, indent=2, ensure_ascii=False))

    print("\n" + "=" * 70)
    print("TEST SERIE 101 (senza fasce)")
    print("=" * 70)
    specs_101 = get_piston_specs(test_101)
    print(f"\n📊 Specs estratte:")
    print(json.dumps(specs_101, indent=2, ensure_ascii=False))

    ebay_101 = map_to_ebay_specifics(specs_101, test_101)
    print(f"\n🏷️ eBay ItemSpecifics:")
    print(json.dumps(ebay_101, indent=2, ensure_ascii=False))
