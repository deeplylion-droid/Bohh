# Climb & Steal Eggs

Modalità Roblox: i giocatori hanno un lotto in cima a una montagna innevata, scendono lungo un
sentiero a tornanti pieno di ostacoli per raccogliere uova di pet sempre più rare, le riportano
su per farle schiudere e guadagnano monete con i pet. Si possono rubare uova e pet agli altri.

- Luogo: `126700834809859` · Universo: `10769912716`
- Server da 8 giocatori, testi in inglese e italiano (lingua scelta in automatico, modificabile nelle opzioni).

## Come si gioca

1. Il primo uovo è già in incubazione: si schiude in pochi secondi e il pet inizia a produrre monete.
2. Le monete si accumulano sulla pedana verde davanti a ogni piedistallo: basta salirci.
3. Si comprano potenziamenti (velocità, forza, zaino, incubatrici, schiusa rapida, lotto più grande, barriera).
4. Si scende dalla vetta: Prati → Bosco → Canyon → Grotte di Cristallo → Cratere Vulcanico.
   Più si scende, più le uova sono rare (9 rarità, 37 pet). Le uova rare pesano e rallentano.
   Ogni 30-45 minuti nel cratere compare un **uovo Ultra** (annunciato a tutti, con una colonna di
   luce visibile da tutta la montagna): pesantissimo, si schiude in un'ora e dà uno dei 5 giganti
   Ultra (Pentadrago, Grifone del Tuono, Komodo Infernale, Titano Rex, Vedova Velenosa), alti
   10 volte gli altri pet. Il gigante sta sul **trono**, la torre dietro il muro di fondo del lotto
   (uno per lotto); vendita, furto e raccolta monete sono sull'altare dentro il lotto.
5. Ostacoli: palle di neve, tronchi e massi che rotolano, tronchi oscillanti, capre che caricano,
   geyser, colate di lava, raffiche di vento, bombe di lava e le mamme guardiane delle tane.
   Ogni 2-3 minuti arriva una valanga: bisogna ripararsi nei rifugi lungo il sentiero.
6. Furti: tenendo premuto per 2 secondi si ruba un uovo o un pet da un lotto altrui. Il ladro
   rallenta, ha la scritta "LADRO!" e se viene colpito con la mazza perde la refurtiva.
   Difese: barriera laser, allarme e trappole (buccia di banana, melma, tagliola).

Eventi automatici (pioggia di meteore, ora d'oro, super valanga), classifiche, album dei pet con
premi, regali giornalieri e a tempo, bonus amici e codici (`LAUNCH`, `EGGS`, `MOUNTAIN`).

## Struttura del progetto

| Cartella | Contenuto |
|---|---|
| `src/shared` | Configurazione (`Config/`: rarità, pet, zone, potenziamenti, prodotti, eventi...), testi EN/IT, mappa, ostacoli, rete |
| `src/server` | Servizi del server (`Services/`), costruzione del mondo (`World/`), avvio (`Boot.luau`) |
| `src/client` | Controller del client (`Controllers/`) e interfaccia (`UI/`) |
| `src/first` | Schermata di caricamento |
| `art` | Script dei modelli 3D (vedi `art/README.md`), uova, pet, oggetti, icone, cielo |
| `tools` | Strumenti: Open Cloud (`rbxcloud.py`), caricamento asset (`upload_assets.py`), test su server (`cloud_test.py`) |
| `tests` | Test d'integrazione su un server Roblox vero e render di controllo |

Il bilanciamento si cambia in `src/shared/Config/` (prezzi, guadagni, tempi di schiusa,
probabilità delle mutazioni, intervallo della valanga...).

## Compilare e pubblicare

```bash
tools/setup.sh                                   # una volta: Rojo, Lune, luau-lsp, Blender (bpy)...
.tools/bin/rojo build default.project.json -o build/ClimbAndStealEggs.rbxl
python tools/rbxcloud.py publish build/ClimbAndStealEggs.rbxl Published
```

Per lavorare in Studio: `.tools/bin/rojo serve` e il plugin Rojo.

Test d'integrazione su un server vero (carica una versione *salvata*, non pubblicata):

```bash
python tools/cloud_test.py tests/cloud/boot_test.luau
```

Anteprima dell'interfaccia senza Roblox: `tests/ui/render_ui.luau` costruisce HUD, pannelli,
schiusa, tutorial e schermata di caricamento con il codice vero del client in un ambiente
simulato (Lune), e `tests/ui/to_html.py` li disegna con Chromium, con sopra la sagoma della chat,
dell'elenco giocatori, della barra degli strumenti e dei comandi touch di Roblox:

```bash
.tools/bin/lune run tests/ui/render_ui.luau          # scene in art/out/ui/*.json
.tools/venv/bin/python tests/ui/to_html.py          # art/out/ui/*.png e contact.png
```

## Modelli 3D, immagini e suoni

I modelli si generano con gli script in `art/` (Blender in modalità libreria) e si caricano con
`python tools/upload_assets.py`, che aggiorna da solo `src/shared/Assets.luau`. I suoni sono
asset della libreria ufficiale di Roblox elencati in `tools/sounds.json`.

## Pannello admin

Il proprietario (e gli id in `Config/Game.luau` → `ExtraAdmins`) vede il pulsante rosso con la
chiave inglese: avvio/stop degli eventi, uova speciali in una zona, valanga immediata, monete e
fortuna di prova, annunci a tutto il server.

## Icona, miniature e pubblicazione

Icona (512×512) e miniature (1920×1080) sono in `art/promo/final/`: si rigenerano con
`art/promo/render_heroes.py` (render dei pet e delle uova senza ombra, dalla cartella `art/`) e
`art/promo/make_promo.py` (composizione in HTML fotografata con Chromium).

Passi da fare a mano su Creator Hub (le API non li permettono):

1. **Prova** il gioco: è pubblicato ma **privato**, quindi può entrare solo il proprietario.
2. **Questionario sulla maturità** dei contenuti (obbligatorio prima di renderlo pubblico).
3. **Icona e miniature**: caricare `icon.png` e `thumbnail_1/2/3.png` nella configurazione
   dell'esperienza.
4. Facoltativo: per il premio "unisciti al gruppo" mettere l'id del gruppo in
   `Config/Game.luau` → `GroupId` (con 0 il pulsante resta nascosto).
5. Quando è tutto pronto: impostare l'esperienza come **pubblica**.

Nome e descrizione (inglese con un paragrafo in italiano), server da 8 giocatori, server privati a
50 R$, game pass e prodotti sono già configurati.
