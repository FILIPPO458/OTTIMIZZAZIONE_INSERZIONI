import requests
from iap_auth import get_token


def get_magazzino_products(token, search_term="", vehicle_id=None):
    """
    Recupera i prodotti dal magazzino usando il token come Bearer.
    Almeno uno tra search_term o vehicle_id deve essere fornito.
    """
    MAGAZZINO_API_URL = "https://api.iapqualityparts.com/Products/SearchProducts"

    # Parametri di ricerca
    params = {}
    if search_term:
        params["search"] = search_term
    if vehicle_id:
        params["vehicleId"] = vehicle_id

    # Header: Bearer token + x-api-key
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": "AV54FG6R",  # La key rimane la stessa
    }

    try:
        response = requests.get(MAGAZZINO_API_URL, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            # Spesso i prodotti sono in data["data"]
            if (
                isinstance(data, dict)
                and "data" in data
                and isinstance(data["data"], list)
            ):
                return data
            else:
                print("Formato della risposta non valido:", data)
                return {"data": []}
        else:
            print(f"Errore HTTP: {response.status_code}")
            print("Dettagli:", response.text)
            return {"data": []}
    except Exception as e:
        print("Eccezione durante il recupero dei prodotti:", str(e))
        return {"data": []}


def main():
    # Inserisci qui il token ottenuto dal file get_token.py
    token = get_token()

    # Esempio: cerchiamo prodotti con la parola "oil"
    products = get_magazzino_products(token, search_term="100-51054")  # 513-14056P 503-14032

    if products:
        print("Prodotti trovati:")
        for p in products.get("data", []):
            print(p)
    else:
        print("Nessun prodotto trovato o errore nell'API.")


if __name__ == "__main__":
    main()
