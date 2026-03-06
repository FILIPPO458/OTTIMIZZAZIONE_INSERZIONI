"""
Modulo per gestione automatica token IAP (versione minimal)
Usa: from iap_auth import get_token
"""

import requests
import jwt
from datetime import datetime, timedelta


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

IAP_TOKEN_URL = "https://api.iapqualityparts.com/Tokens/GetAccessToken"
IAP_USERNAME = "API_BCCPARTS"
IAP_PASSWORD = "4$t96_3G"
IAP_KEY = "AV54FG6R"


# ============================================================================
# CACHE IN MEMORIA
# ============================================================================

_token_cache = None
_token_expiry = None


# ============================================================================
# FUNZIONI PUBBLICHE
# ============================================================================


def get_token(silent=False):
    """
    Ottiene token IAP valido (usa cache in memoria o richiede nuovo)

    Args:
        silent: Se True, non stampa messaggi (default: False)

    Returns:
        str: Access token valido
    """
    global _token_cache, _token_expiry

    # Controlla cache in memoria (margine 5 minuti)
    if _token_cache and _token_expiry:
        if datetime.now() < (_token_expiry - timedelta(minutes=5)):
            if not silent:
                print("✓ Token IAP valido (cache)")
            return _token_cache

    # Richiedi nuovo token
    if not silent:
        print("⟳ Richiesta nuovo token IAP...")

    params = {"username": IAP_USERNAME, "password": IAP_PASSWORD, "key": IAP_KEY}

    response = requests.get(IAP_TOKEN_URL, params=params)

    if response.status_code != 200:
        raise Exception(f"Errore IAP API: {response.status_code}")

    data = response.json()

    if not data.get("success") or not data.get("data"):
        raise Exception("Errore: token IAP non ricevuto")

    token_list = data["data"]
    if not isinstance(token_list, list) or len(token_list) == 0:
        raise Exception("Errore: formato risposta IAP non valido")

    new_token = token_list[0]

    # Decodifica JWT per ottenere scadenza
    try:
        decoded = jwt.decode(new_token, options={"verify_signature": False})
        exp_timestamp = decoded.get("exp")

        if exp_timestamp:
            _token_expiry = datetime.fromtimestamp(exp_timestamp)
        else:
            # Default 1 ora se non c'è exp
            _token_expiry = datetime.now() + timedelta(hours=1)
    except:
        # Default 1 ora se decodifica fallisce
        _token_expiry = datetime.now() + timedelta(hours=1)

    _token_cache = new_token

    if not silent:
        print(f"✓ Nuovo token IAP ottenuto (scade: {_token_expiry})")

    return new_token


def get_headers():
    """
    Ottiene headers pronti per chiamate API IAP

    Returns:
        dict: Headers con Authorization e Content-Type
    """
    token = get_token(silent=True)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST MODULO IAP AUTH (MINIMAL)")
    print("=" * 60 + "\n")

    try:
        # Test get_token
        token = get_token()
        print(f"\nToken ottenuto: {token[:50]}...")

        # Test cache (seconda chiamata)
        print("\n--- Test cache (seconda chiamata) ---")
        token2 = get_token()
        print("Token da cache:", token == token2)

        # Test get_headers
        headers = get_headers()
        print(f"\nHeaders pronti per API calls")

        print("\n" + "=" * 60)
        print("✓ MODULO FUNZIONANTE")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Errore: {e}")
