# extract_piston_specs.py
import json
import requests
import base64
import re
import os
import logging
import time
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

# ============================================================================
# CONFIGURAZIONE
# ============================================================================
# 2. Carichi il file
load_dotenv("/Users/filippocambareri/.bcc_secrets/ebay.env")
# Variabili d'ambiente (BEST PRACTICE per produzione)
ANTHROPIC_API_KEY = os.environ.get(
    "ANTHROPIC_API_KEY"
)  # Assicurati di avere questa variabile nel tuo .env

# Cache per evitare chiamate duplicate a Claude
CACHE_FILE = "piston_specs_cache.json"

# Logging configurato
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("piston_extraction.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

IAP_ATTRIBUTES_MAP = {
    211810: "diametro_pistone",  # Diametro pistone [mm]
    210724: "diametro_spinotto",  # Bullone-Ø [mm]
    211177: "altezza_compressione",  # Altezza di compressione [mm]
    211168: "spessore_fascia_1",  # Spessore 1 [mm]
    211169: "spessore_fascia_2",  # Spessore 2 [mm]
    210124: "spessore_fascia_olio",  # Spessore [mm] (la terza fascia)
    210203: "lunghezza_totale",  # Lunghezza [mm]
    210596: "info_integrativa",
    213217: "numero_pezzi",  # Articolo complementare/Info integrativa
}

REQUIRED_FIELDS = ["diametro_pistone", "diametro_spinotto"]

# ============================================================================
# CACHE MANAGEMENT
# ============================================================================


def load_cache():
    """Carica cache da file JSON"""
    if Path(CACHE_FILE).exists():
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_cache(cache):
    """Salva cache su file JSON"""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


# Cache globale
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

    # Estrai solo numeri, punti e virgole
    match = re.search(r"[0-9]+[.,]?[0-9]*", str(value))
    if match:
        cleaned = match.group(0).replace(",", ".")
        return cleaned
    return None


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
            if field_name in [
                "bore_diameter",
                "pin_diameter",
                "compression_height",
                "length",
                "ring_top",
                "ring_second",
                "ring_oil",
            ]:
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
# STEP 2: DOWNLOAD IMMAGINE (con retry e gestione errori)
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
                # Determina media_type da Content-Type header (più affidabile)
                media_type = response.headers.get("Content-Type", "image/jpeg")

                # Fallback su estensione se Content-Type non valido
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
                time.sleep(2**attempt)  # exponential backoff

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
# STEP 3: CLAUDE VISION (con retry e cache)
# ============================================================================


def extract_with_claude(image_url, mpn, max_retries=3):
    """
    Estrae dati con Claude Vision API
    Usa cache per evitare chiamate duplicate
    """
    # Check cache prima
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

    # Prompt migliorato con istruzioni più precise
    prompt = """Analizza questo disegno tecnico di un pistone motore.

ISTRUZIONI:
- Estrai SOLO valori numerici in millimetri
- Se ci sono più diametri, prendi il valore principale (bore diameter)
- Ignora quote tra parentesi o annotazioni
- Per le fasce (rings): TOP, 2nd, Oil in quest'ordine
- Se un valore non è chiaramente leggibile, usa null

Rispondi SOLO con JSON valido (NO markdown, NO testo):
{
  "bore_diameter": "valore",
  "pin_diameter": "valore",
  "compression_height": "valore",
  "length": "valore",
  "ring_top": "valore",
  "ring_second": "valore",
  "ring_oil": "valore",
  "material": "descrizione materiale"
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

            specs = json.loads(response_text)

            # Pulizia valori numerici da Claude
            for key in [
                "bore_diameter",
                "pin_diameter",
                "compression_height",
                "length",
                "ring_top",
                "ring_second",
                "ring_oil",
            ]:
                if key in specs and specs[key]:
                    specs[key] = clean_numeric_value(specs[key])

            # Salva in cache
            _cache[cache_key] = specs
            save_cache(_cache)

            logger.info("   ✅ Dati estratti")
            return specs

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
    Strategia ibrida con logging completo:
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

    # Step 3: Merge
    specs_final = {**specs_claude, **specs_iap}

    logger.info(f"   📊 Specs finali: {len(specs_final)} campi")
    return specs_final


# ============================================================================
# STEP 5: MAPPING EBAY
# ============================================================================
def is_serie_100(mpn):
    """Verifica se è Serie 100 (completa con fasce)"""
    return mpn.startswith("100-")


def is_serie_101(mpn):
    """Verifica se è Serie 101 (senza fasce)"""
    return mpn.startswith("101-")


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

    # Diametro pistone - prova ENTRAMBI i nomi (italiano E inglese)
    if specs.get("diametro_pistone") or specs.get("bore_diameter"):
        diameter = specs.get("diametro_pistone") or specs.get("bore_diameter")
        nvl.append({"Name": "Diametro del pistone", "Value": f"{diameter} mm"})
        nvl.append({"Name": "Diametro del foro del cilindro", "Value": f"{diameter} mm"})

    # Diametro spinotto - prova ENTRAMBI i nomi (italiano E inglese)
    if specs.get("diametro_spinotto") or specs.get("pin_diameter"):
        pin_diam = specs.get("diametro_spinotto") or specs.get("pin_diameter")
        nvl.append({"Name": "Diametro dello spinotto", "Value": f"{pin_diam} mm"})

    # 🆕 TRONCAMENTO MATERIALE A 65 CARATTERI
    if specs.get("materiale") or specs.get("info_integrativa"):
        material = specs.get("materiale") or specs.get("info_integrativa")
        # Tronca a 65 caratteri max per eBay
        if len(material) > 65:
            material = material[:62] + "..."
        nvl.append({"Name": "Materiale", "Value": material})
        # ✅ AGGIUNGI QUI - Articoli inclusi con logica Serie 100/101
    if is_serie_100(mpn):
        nvl.append(
            {
                "Name": "Articoli inclusi",
                "Value": [
                    "Pistone",
                    "Anelli per pistone",
                    "Spinotto",
                    "Fermo",
                ],
            }
        )
    elif is_serie_101(mpn):
        nvl.append(
            {
                "Name": "Articoli inclusi",
                "Value": ["Pistone", "Spinotto", "Fermo"],
            }
        )

    # ✅ AGGIUNGI QUI - Numero pistoni nel kit
    if specs.get("numero_pezzi"):
        nvl.append(
            {"Name": "Numero di pistoni nel kit", "Value": specs["numero_pezzi"]}
        )
    nvl.append({"Name": "Peso", "Value": "2 kg"})
    extras = []
    if specs.get("compression_height"):
        extras.append(f"Altezza: {specs['compression_height']} mm")
    if specs.get("length"):
        extras.append(f"Lunghezza: {specs['length']} mm")
    if specs.get("ring_top"):
        rings = f"{specs['ring_top']}/{specs.get('ring_second', '?')}/{specs.get('ring_oil', '?')}"
        extras.append(f"Fasce: {rings} mm")

    if extras:
        nvl.append(
            {
                "Name": "Articolo complementare/Info integrativa",
                "Value": ", ".join(extras),
            }
        )

    return {"ItemSpecifics": {"NameValueList": nvl}}


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    test_product = {
        "manufacturerProductVariantCode": "100-51054",
        "image": "https://www.iapqualityparts.com/img-server/productmasters/details/100-51054.jpg",
        "attributes": [
            {"attributeId": 211810, "value": "84"},
            {"attributeId": 210724, "value": "30"},
        ],
    }

    specs = get_piston_specs(test_product)
    print(f"\n📊 Specs estratte:")
    print(json.dumps(specs, indent=2, ensure_ascii=False))

    ebay = map_to_ebay_specifics(specs, test_product)
    print(f"\n🏷️ eBay ItemSpecifics:")
    print(json.dumps(ebay, indent=2, ensure_ascii=False))
