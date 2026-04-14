# Agent: eBay OE Code Enricher
# Versione: 2.0 — Produzione
# Scopo: Arricchire le inserzioni eBay con codici OE originali del costruttore

---

## Obiettivo
Leggi il file `ebay-active-listings-report.csv` e per ogni inserzione trova
i codici OE originali del costruttore. Produci un CSV aggiornato pronto
per il re-upload su eBay File Exchange.

---

## Salvataggio progressivo — OBBLIGATORIO

- Salva ogni 50 inserzioni processate in `ebay_OE_output.csv` (modalità append)
- Dopo ogni batch aggiorna `progresso.json`:

```json
{
  "ultima_riga_processata": 0,
  "totale_trovati": 0,
  "totale_non_trovati": 0,
  "totale_bloccati": 0,
  "ultima_esecuzione": "",
  "categoria_corrente": ""
}
```

## Ripartenza dopo interruzione
- All'avvio leggi sempre `progresso.json`
- Se esiste: riparti dall'ultima riga processata, non da capo
- Non riprocessare mai inserzioni già presenti in `ebay_OE_output.csv`
- Logga ogni errore in `errori.log` con timestamp e motivo

---

## Ordine di lavorazione per categoria

Processa in questo ordine (dal volume più alto al più basso):

1. Kit frizione (~3921 inserzioni)
2. Bracci controllo, giunti sferici e assemblaggi (~2181)
3. Pistoni e anelli (~1890)
4. Bronzine motore (~1695)
5. Pastiglie dei freni (~1431)
6. Guarnizioni e sigilli (~1295)
7. Pompe dell'acqua (~1266)
8. Altro auto: ricambi e accessori (~1093)
9. Barre antirollio, collegamenti e boccole (~1028)
10. Freni a disco (~951)
11. Tutte le categorie rimanenti

---

## Strategia di ricerca OE — Priorità assoluta

### Step 1 — SKU IAP (priorità massima)
Lo SKU IAP (colonna `Custom label (SKU)`, formato `100-XXXXX`) è il punto
di partenza più efficace. Cerca prima:

```
"[SKU_IAP] codice OE"
"[SKU_IAP] OEM reference"
"[SKU_IAP] original part number"
```

Esempi di query:
- `"100-00103 codice OE"`
- `"100-00103 OEM cross reference"`

### Step 2 — Titolo inserzione
Estrai dal titolo: marca auto, modello, tipo ricambio, eventuale codice
aftermarket (LUK, Sachs, Valeo, Febi, Gates, SKF ecc.).

Se il titolo contiene un codice di marca aftermarket, cerca la conversione:
```
"LUK 123456789 codice OE originale"
"Sachs 3000123456 OEM equivalent"
```

### Step 3 — Ricerca web (usa web search nativo, NON scraping diretto)
Usa il tool di ricerca web integrato con queste query in ordine:

**Per auto europee:**
1. `[marca] [modello] [tipo_ricambio] codice OE originale`
2. `[SKU_IAP] OEM part number site:autodoc.it`
3. `[marca] [modello] [tipo_ricambio] numero originale costruttore`

**Per auto asiatiche (Toyota, Honda, Nissan, Hyundai, Kia):**
1. `[marca] [modello] [tipo_ricambio] OEM part number site:partsouq.com`
2. `[marca] [modello] [tipo_ricambio] site:7zap.com`
3. `[SKU_IAP] OEM reference Asia`

**Fonti di riferimento (in ordine di priorità):**
1. autodoc.it / autodoc.de
2. mister-auto.com
3. mecadepot.com
4. partsouq.com (auto asiatiche)
5. 7zap.com (auto asiatiche)
6. tuttoauto.it
7. realoem.com (BMW/MINI)
8. erwin.bmw.de (BMW)
9. etka.net (Gruppo VW)

### Step 4 — Gestione blocchi anti-bot
Se una fonte restituisce CAPTCHA, errore 403, o non risponde:
- Segna nel log: `BLOCCATO_DA_SITO: [nome_sito]`
- Passa immediatamente alla fonte successiva
- Non riprovare lo stesso sito per le successive 100 inserzioni
- Se tutte le fonti sono bloccate: stato = `BLOCCATO_DA_SITO`

---

## Regole qualità codici OE

### Validazione
- Confronta SEMPRE almeno 2 fonti prima di confermare un codice OE
- Se le fonti non concordano: stato = `VERIFICA`
- MAI inventare o ipotizzare un codice OE
- Se non trovi nulla di certo: stato = `NON_TROVATO`

### Formati OE per costruttore (standardizzazione)
Rimuovi spazi, punti e trattini SOLO se non fanno parte del formato ufficiale:

| Costruttore | Formato originale | Esempio |
|-------------|------------------|---------|
| BMW/MINI | 11 cifre con spazi | `11 12 1 234 567` → salva come `11121234567` |
| Volkswagen/Audi/Seat/Skoda | Alfanumerico con spazi | `1K0 123 456 A` → salva come `1K0123456A` |
| Mercedes | 10 cifre con punti | `123.456.78.90` → salva come `1234567890` |
| Fiat/Alfa/Lancia | Numerico puro | `46543210` |
| Ford | Alfanumerico | `1234567` |
| Opel/Vauxhall | Numerico | `1234567` |
| Peugeot/Citroën | Numerico con spazi | `1234.56` → `123456` |
| Renault | Numerico | `7700123456` |
| Toyota/Honda/Nissan | Alfanumerico | `31250-36090` → salva con trattino |
| Hyundai/Kia | Alfanumerico | `41300-32810` → salva con trattino |

**Regola generale:** salva il codice nel formato più comune usato nei
cataloghi ufficiali del costruttore. Escludi sempre spazi iniziali/finali.

### Filtro rumore — Escludi questi codici
- Codici EAN/barcode (13 cifre numeriche pure)
- Numeri di spedizione/tracking
- Codici aftermarket puri (es. LUK 123456789 senza corrispondenza OE)
- Numeri generici sotto 5 caratteri

### Gestione Kit (frizioni, guarnizioni, ecc.)
Per i KIT cerca ENTRAMBI:
1. **Codice kit completo** (preferito) — es. kit frizione completo
2. **Codici singoli componenti** se il codice kit non esiste

Salva nel campo `OE_codes` separati da `|`:
```
1234567890|0987654321|1122334455
```
Indica nel campo `OE_note` se sono kit o singoli componenti:
```
kit_completo | disco+spingidisco+cuscinetto
```

---

## Formato output CSV

Il file `ebay_OE_output.csv` deve avere TUTTE le colonne originali più:

| Colonna aggiunta | Descrizione |
|-----------------|-------------|
| `OE_codes` | Codici OE separati da `\|` |
| `OE_costruttore` | Es: BMW, FIAT, VOLKSWAGEN |
| `OE_status` | TROVATO / NON_TROVATO / VERIFICA / BLOCCATO_DA_SITO |
| `OE_fonte` | Sito/i da cui hai preso il codice |
| `OE_tipo` | kit_completo / componente_singolo / multiplo |
| `OE_note` | Note aggiuntive (es. "disco+spingidisco+cuscinetto") |

---

## Gestione errori e log

Crea e aggiorna continuamente `errori.log`:
```
[2026-04-14 15:30:22] RIGA 1250 | SKU 100-00103 | ERRORE: autodoc.it timeout
[2026-04-14 15:30:25] RIGA 1250 | SKU 100-00103 | OK: trovato su mister-auto.com
[2026-04-14 15:31:10] RIGA 1251 | SKU 100-00114 | BLOCCATO: cloudflare su tutti i siti
```

---

## Regole generali di comportamento

- Non bloccarti mai su una singola inserzione — max 60 secondi per inserzione
- Se una inserzione non ha titolo leggibile: `NON_TROVATO` e vai avanti
- Priorità alla velocità + accuratezza: meglio `NON_TROVATO` onesto che codice sbagliato
- Alla fine di ogni categoria: stampa un riepilogo nel log
- Al completamento totale: genera `riepilogo_finale.txt` con statistiche complete

---

## Comando di avvio

```bash
# Prima esecuzione
claude "Processa tutte le inserzioni in ebay-active-listings-report.csv 
e trovami i codici OE. Segui le istruzioni nel CLAUDE.md."

# Ripresa dopo interruzione
claude "Controlla progresso.json e riprendi da dove eri rimasto."
```