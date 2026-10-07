# The Rake: Caccia nei Boschi — modalità per Roblox

Survival-horror cooperativo per 1–8 giocatori. La squadra parte dalla Ranger Station, al centro di
un bosco notturno, per **localizzare, tracciare e catturare** The Rake. L'arma principale è la
ricognizione: piazzare telecamere, raccogliere prove e osservare i feed prima che la creatura colpisca.

## Ciclo di gioco

1. **Briefing (30 s)** alla Ranger Station: nuovo bosco, meteo e obiettivo estratti a caso.
2. **Notte (10 min, dalle 20:00 alle 06:00)**: si esplora, si piazzano telecamere, si raccolgono prove.
3. **Confronto**: la creatura si stordisce con 4 dardi tranquillanti, poi si cattura tenendo premuto E.
4. **Debriefing**: XP e ranghi in base a prove, telecamere utili, rianimazioni, cattura e risultato.
   In caso di sconfitta gli XP sono dimezzati.

### Obiettivi (uno per notte)

| Obiettivo | Come si vince |
| --- | --- |
| Ricognizione | 4 telecamere attive contemporaneamente e 3 prove documentate |
| Caccia | Catturare The Rake |
| Sopravvivenza | Almeno un giocatore in piedi all'alba (creatura più aggressiva) |
| Reperto | Riportare alla stazione il nastro audio nascosto in un punto di interesse |

La cattura vale come vittoria con qualsiasi obiettivo. Si perde se tutta la squadra è a terra o se
sorge l'alba prima di completare l'obiettivo.

## Meccaniche

- **Mappa**: bosco di 800×800 stud con 4 biomi (pineta fitta, ruderi del campeggio, palude, miniera),
  sentieri e punti di interesse fissi: Ranger Station, torre di avvistamento, campeggio, lago con
  pontile, capanno, miniera. Gli alberi vengono rigenerati a ogni partita. Ciclo notte/alba e meteo
  (sereno, nebbia, pioggia) che riduce visibilità e affidabilità delle camere.
- **Telecamere** (tasto 2, clic per piazzarle davanti a te, R per cambiare tipo):
  Fissa ×2, IR ×1 (vede al buio), Motorizzata ×1 (si ruota dal tablet), Trappola ×1 (scatta una foto
  quando la creatura passa). Hanno una batteria; con E le recuperi e le ricarichi. Quando una camera
  inquadra la creatura la barra di Tracciamento sale e la posizione appare sulla mappa.
- **Tablet** (tasto T o la sala di controllo della stazione): feed live, visione IR, interferenze
  quando la creatura è vicina alla camera, mini-mappa con camere, compagni e area di caccia.
- **Prove**: impronte, graffi, peli, sangue e carcasse vicino alla tana e lungo il percorso della
  creatura. Peli e sangue vanno analizzati al laboratorio (12 s di rumore che la attira). Alcune tracce
  sono depistaggi. Il Tracciamento rivela la zona della tana (30%), un'area di caccia segnata in rosso
  (65%) e infine la posizione esatta a intervalli (100%).
- **The Rake**: IA a stati Inattiva → Curiosa (ti pedina) → Territoriale (ti gira intorno e finge
  cariche) → Aggressiva (attacca), più Fuga e Stordita. L'aggressività cresce con la notte, la corsa,
  le torce viste da lontano e i giocatori isolati. Punta chi è solo o porta il nastro, evita la stazione
  finché non è Aggressiva. Teme la luce: una torcia puntata da vicino per 1,5 s la mette in fuga.
- **Sopravvivenza**: stamina con fiatone (Shift), Paura che sale al buio e da soli e scende vicino ai
  compagni e alle luci (al massimo: allucinazioni e movimenti più lenti), visore notturno (N) a
  batteria. Se la creatura ti prende sei **Braccato**: un compagno ha 30 s per rianimarti.
- **Attrezzatura**: torcia (1) con batteria, telecamere (2), fucile a dardi tranquillanti (3, 6 dardi).
  Il Rifornimento della stazione ricarica dardi, torcia e visore. Nessuna arma letale.
- **Progressione**: XP, livello e rango *Novizio → Ricercatore → Cacciatore → Veterano → Leggenda*,
  salvati con DataStore e mostrati nella classifica.

Tutti i valori di bilanciamento sono in `src/shared/Config.luau`, compresi i suoni: la creatura usa
suoni 3D, quindi conviene impostare `RAKE_CALL` e `RAKE_SCREECH` con audio del Creator Store.

## Struttura

| File | Dove va in Studio | Tipo |
| --- | --- | --- |
| `src/shared/Config.luau` | `ReplicatedStorage > Shared > Config` | ModuleScript |
| `src/server/RakeHunt/init.server.luau` | `ServerScriptService > RakeHunt` | Script |
| `src/server/RakeHunt/*.luau` | figli di `RakeHunt` (Forest, Rake, Cameras, Evidence, Team, Objectives, Progression) | ModuleScript |
| `src/client/RakeClient/init.client.luau` | `StarterPlayer > StarterPlayerScripts > RakeClient` | LocalScript |
| `src/client/RakeClient/*.luau` | figli di `RakeClient` (Hud, Tablet) | ModuleScript |

Mappa, luci, creatura e interfaccia vengono creati dagli script, quindi il luogo può partire vuoto.

## Installazione

Apri `build/TheRake.rbxlx` con Roblox Studio e pubblicalo con *File → Publish to Roblox*.
Se modifichi gli script in `src/`, rigenera il file con `python3 tools/build_place.py`
(oppure usa Rojo: `rojo serve` / `rojo build`, il progetto è `default.project.json`).

In Studio, per provare il salvataggio dei progressi attiva *Game Settings → Security → Enable Studio
Access to API Services*.

## Non ancora incluso

Dal documento di design mancano: albero delle abilità, album dei criptidi, droni e registratore
audio, eventi settimanali e tutta la monetizzazione (abbonamento Pro, valuta "Pelliccia", Battle
Pass, bundle cosmetici), che richiede di creare pass e prodotti nella dashboard di Roblox.
