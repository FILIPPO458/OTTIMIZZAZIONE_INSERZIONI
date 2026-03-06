def build_enhanced_description(product: dict, custom_paragraph: str = "") -> str:
    """Costruisce descrizione HTML usando ESATTAMENTE le stesse variabili di map_basic_item"""

    # STESSO CODICE DI map_basic_item
    code = product.get("manufacturerProductVariantCode", "")
    brand = product.get("brand", "").strip()
    if brand.upper() == "QUALITY PARTS":
        brand = f"IAP {brand}"
    tipo = product.get("description", "")

    # STESSI ATTRIBUTI DI map_basic_item
    attrs = {a["name"]: a["value"] for a in product.get("attributes", [])}

    # STESSE IMMAGINI DI map_basic_item
    images = [u for u in (product.get("image"), product.get("image2")) if u]
    img = images[0] if images else ""

    # STESSE SPECIFICHE DI map_basic_item (nvl)
    specs = [
        ("Codice Prodotto", code),
        ("Marca", attrs.get("Marca", brand or "Generico")),
        ("Tipo ammortizzatore", tipo),
        ("Diametro [mm]", attrs.get("Diametro [mm]", "")),
        ("Lato montaggio", attrs.get("Lato montaggio", "")),
        ("Lunghezza max. [mm]", attrs.get("Lunghezza max. [mm]", "")),
        ("Lunghezza min. [mm]", attrs.get("Lunghezza min. [mm]", "")),
    ]

    # HTML con CDATA per evitare errori XML
    return f"""<![CDATA[
<div style="font-family:Arial;max-width:800px;margin:0 auto">
<h2>{code} {brand} {tipo}</h2>
{f'<img src="{img}" style="display:block;margin:20px auto;max-width:400px" />' if img else ''}
<div style="background:#f8f9fa;padding:15px;border-left:4px solid #007bff;margin:20px 0">
{custom_paragraph if custom_paragraph else '''
<h3 style="color:#007bff;margin-top:0">Benvenuto nel nostro negozio Bologna Classic Cars</h3>
<p>Siamo specializzati nella fornitura di ricambi ORIGINALI e AFTERMARKET per ogni tipo di veicolo.</p>
<ul style="margin:10px 0">
<li><strong>Qualità certificata:</strong> Ogni componente è selezionato secondo i più elevati standard</li>
<li><strong>Assistenza tecnica:</strong> Supporto professionale pre e post-vendita</li>
</ul>
<p style="background:#fff3cd;padding:10px;border-radius:5px;margin:15px 0">
<strong>⚠️ IMPORTANTE:</strong> Verifica sempre la compatibilità del ricambio con il tuo veicolo ,inviaci il libretto di circolazione o il telaio per conferma
</p>
<p style="background:#d4edda;padding:10px;border-radius:5px">
<strong>💡 Nota:</strong> Su eBay è visibile meno del 15% del nostro catalogo. Se non trovi il ricambio che cerchi, scrivici!
 <a href="https://www.ebay.it/cnt/intermediatedFAQ?requested=bolognaclassiccars"
     target="_blank"
     rel="noopener noreferrer"
     style="color:#007bff;font-weight:bold;text-decoration:underline">
     scrivici!
  </a></p>
  <!-- CALL-TO-ACTION: visita o segui il negozio -->
<div style="text-align:center;margin:28px 0">
  <!-- Pulsante visita negozio -->
  <a href="https://www.ebay.it/str/bolognaclassiccars"
     target="_blank"
     rel="noopener noreferrer"
     style="
        background:#28a745;
        color:#fff;
        padding:12px 26px;
        border-radius:6px;
        font-weight:bold;
        text-decoration:none;
        display:inline-block;
        margin-right:10px">
     🛒 Visita il nostro negozio
  </a>
  <!-- Pulsante segui negozio -->
  <a href="https://my.ebay.it/ws/eBayISAPI.dll?AcceptSavedSeller&sellerid=BolognaClassicCars"
     target="_blank"
     rel="noopener noreferrer"
     style="
        background:#007bff;
        color:#fff;
        padding:12px 26px;
        border-radius:6px;
        font-weight:bold;
        text-decoration:none;
        display:inline-block">
     ⭐ Segui il nostro negozio
  </a>
</div>
'''}
</div>
<h3>Specifiche</h3>
<table style="width:100%;border-collapse:collapse">
{''.join(f'<tr><td style="border:1px solid #ddd;padding:10px"><b>{k}</b></td><td style="border:1px solid #ddd;padding:10px">{v}</td></tr>' for k,v in specs if v)}
</table>
<p style="background:#e8f5e8;padding:15px;margin-top:20px">🚚 Spedizione Gratuita 1-3 giorni</p>
</div>

]]>"""
