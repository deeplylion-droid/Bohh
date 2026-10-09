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
   Più si scende, più le uova sono rare (8 rarità, 32 pet). Le uova rare pesano e rallentano.
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

## Modelli 3D, immagini e suoni

I modelli si generano con gli script in `art/` (Blender in modalità libreria) e si caricano con
`python tools/upload_assets.py`, che aggiorna da solo `src/shared/Assets.luau`. I suoni sono
asset della libreria ufficiale di Roblox elencati in `tools/sounds.json`.

## Pannello admin

Il proprietario (e gli id in `Config/Game.luau` → `ExtraAdmins`) vede il pulsante rosso con la
chiave inglese: avvio/stop degli eventi, uova speciali in una zona, valanga immediata, monete e
fortuna di prova, annunci a tutto il server.
