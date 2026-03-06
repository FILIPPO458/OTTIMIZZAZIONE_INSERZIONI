import requests
from iap_auth import get_token as get_iap_token
from datetime import datetime

def get_shipping_documents(token):
    url = "https://api.iapqualityparts.com/ShippingDocuments/GetShippingDocuments"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": "AV54FG6R"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        response_json = response.json()
        
        if not response_json.get("success"):
            print("Errore nella risposta dell'API:", response_json.get("message"))
            return None

        raw_docs = response_json.get("data", [[]])[0]  # prende la lista interna

        ebay_docs = []
        for doc in raw_docs:
            ebay_doc = {
                "trackingNumber": doc.get("shippingCode"),  # uso shippingCode come identificatore
                "shippingCarrierCode": convert_carrier_name(doc.get("shippingCarrierDescription")),
                "shippedDate": format_shipping_date(doc.get("shippingDateTime")),
                "orderId": doc.get("originalSalesOrder"),  # opzionale ma utile
                "buyerReference": doc.get("customerReference")
            }
            ebay_docs.append(ebay_doc)

        return ebay_docs

    else:
        print(f"Errore HTTP: {response.status_code}")
        print("Dettagli:", response.text)
        return None

def convert_carrier_name(carrier):
    """Converte il nome del corriere nel formato accettato da eBay."""
    mapping = {
        "MBE-GLS": "GLS",
        "SUD TRASPORTI": "Other",
        "BOLOGNA CLASSIC CARS": "Other"
    }
    return mapping.get(carrier, "Other")

def format_shipping_date(date_str):
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    except Exception as e:
        print(f"Errore nella data: {e}")
        return None

if __name__ == "__main__":
    token = get_iap_token()
    docs = get_shipping_documents(token)
    print("📦 Documenti spedizione per eBay:")
    for d in docs:
        print(d)
