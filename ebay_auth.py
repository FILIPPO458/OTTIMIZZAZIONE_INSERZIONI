"""
Modulo per gestione automatica token eBay
Usa: from ebay_auth import get_token
"""

from dotenv import load_dotenv
import requests
import base64
import webbrowser
from urllib.parse import urlencode, unquote
import json
import os
from datetime import datetime, timedelta

load_dotenv("/Users/filippocambareri/.bcc_secrets/ebay.env")
# ============================================================================
# CONFIGURAZIONE - Modifica questi valori
# ============================================================================
CLIENT_ID = os.environ.get("EBAY_APP_ID")
CLIENT_SECRET = os.environ.get("EBAY_CERT_ID")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
DEV_ID = os.environ.get("EBAY_DEV_ID")
ENVIRONMENT = "production"  # o "sandbox"

SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
    "https://api.ebay.com/oauth/api_scope/sell.account",
]

TOKEN_FILE = "/Users/filippocambareri/.bcc_secrets/ebay_tokens.json"

# URL in base all'ambiente
if ENVIRONMENT == "sandbox":
    AUTH_URL = "https://auth.sandbox.ebay.com/oauth2/authorize"
    TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    API_BASE = "https://api.sandbox.ebay.com"
else:
    AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
    TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    API_BASE = "https://api.ebay.com"


# ============================================================================
# FUNZIONI INTERNE
# ============================================================================


def _salva_token(token_data):
    """Salva token in JSON preservando il refresh_token se non inviato di nuovo"""
    old_data = _carica_token() or {}

    expires_in = token_data.get("expires_in", 7200)
    expiry = datetime.now() + timedelta(seconds=expires_in)

    # CRITICO: Prende il nuovo refresh_token se c'è, altrimenti tiene quello vecchio
    refresh_token = token_data.get("refresh_token") or old_data.get("refresh_token")

    data = {
        "access_token": token_data["access_token"],
        "refresh_token": refresh_token,
        "expiry_time": expiry.isoformat(),
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


def _carica_token():
    """Carica token da file se esiste"""
    if not os.path.exists(TOKEN_FILE):
        return None

    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except:
        return None


def _token_valido(token_data):
    """Controlla se token è ancora valido (margine 5 min)"""
    if not token_data or "expiry_time" not in token_data:
        return False

    try:
        expiry = datetime.fromisoformat(token_data["expiry_time"])
        return datetime.now() < (expiry - timedelta(minutes=5))
    except:
        return False


def _refresh_token(refresh_token):
    """Rinnova access token"""
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {creds}",
    }

    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}

    resp = requests.post(TOKEN_URL, headers=headers, data=data)

    if resp.status_code == 200:
        return resp.json()
    else:
        raise Exception(f"Refresh fallito: {resp.status_code}")


def _nuovo_login():
    """Esegue flusso OAuth completo"""
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print("\n" + "=" * 60)
    print("LOGIN EBAY RICHIESTO")
    print("=" * 60)
    print(f"\nApri questo URL:\n{auth_url}\n")

    webbrowser.open(auth_url)

    code = input("Incolla il 'code' dall'URL di redirect: ").strip()
    code = unquote(code)  # Decodifica se URL-encoded

    if not code:
        raise Exception("Nessun codice fornito")

    # Scambia code con token
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {creds}",
    }

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    resp = requests.post(TOKEN_URL, headers=headers, data=data)

    if resp.status_code == 200:
        return resp.json()
    else:
        raise Exception(f"Errore token: {resp.status_code} - {resp.text}")


# ============================================================================
# FUNZIONI PUBBLICHE - Usa queste nei tuoi script
# ============================================================================


def get_token(silent=False):
    """
    Ottiene sempre un token valido (riuso, refresh, o nuovo login)

    Args:
        silent: Se True, non stampa messaggi (default: False)

    Returns:
        str: Access token valido
    """
    token_data = _carica_token()

    # Token valido esistente
    if token_data and _token_valido(token_data):
        if not silent:
            print("✓ Token valido")
        return token_data["access_token"]

    # Prova refresh
    if token_data and token_data.get("refresh_token"):
        if not silent:
            print("⟳ Refresh token...")
        try:
            new_token = _refresh_token(token_data["refresh_token"])
            _salva_token(new_token)
            if not silent:
                print("✓ Token rinnovato")
            return new_token["access_token"]
        except:
            if not silent:
                print("⚠ Refresh fallito")

    # Nuovo login
    token_response = _nuovo_login()
    _salva_token(token_response)
    if not silent:
        print("✓ Nuovo token ottenuto")
    return token_response["access_token"]


def get_headers():
    """
    Ottiene headers pronti per chiamate API eBay

    Returns:
        dict: Headers con Authorization e Content-Type
    """
    token = get_token(silent=True)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def api_call(method, endpoint, **kwargs):
    """
    Esegue una chiamata API eBay con gestione automatica token

    Args:
        method: 'GET', 'POST', 'PUT', 'DELETE'
        endpoint: Percorso API (es: '/sell/inventory/v1/inventory_item')
        **kwargs: Parametri aggiuntivi per requests (json, params, etc)

    Returns:
        Response object di requests
    """
    headers = get_headers()
    url = f"{API_BASE}{endpoint}"

    return requests.request(method, url, headers=headers, **kwargs)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST MODULO EBAY AUTH")
    print("=" * 60 + "\n")

    try:
        # Test get_token
        token = get_token()
        print(f"\nToken ottenuto: {token[:50]}...")

        # Test get_headers
        headers = get_headers()
        print(f"\nHeaders pronti per API calls")

        print("\n" + "=" * 60)
        print("✓ MODULO FUNZIONANTE")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Errore: {e}")
