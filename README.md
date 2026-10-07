# Coin Rush — modalità di gioco per Roblox

Una modalità a round: i giocatori vengono portati su un'arena sospesa nel cielo e hanno
90 secondi per raccogliere più monete possibile. Chi cade dall'arena o muore è eliminato.
Vince il sopravvissuto con più monete e guadagna un punto in **Vittorie**.

## Come funziona

1. **Attesa** finché non ci sono abbastanza giocatori (`MIN_PLAYERS`).
2. **Intervallo** di 15 secondi nella lobby.
3. **Round**: teletrasporto nell'arena, le monete compaiono a caso (anche in cima ai pilastri).
4. **Risultati**: viene annunciato il vincitore, poi tutti tornano nella lobby.

L'arena, la lobby (se manca uno SpawnLocation) e l'HUD vengono creati automaticamente dagli
script, quindi funziona anche partendo da un luogo vuoto ("Baseplate").

## Struttura

| File | Dove va in Studio | Tipo |
| --- | --- | --- |
| `src/shared/Config.luau` | `ReplicatedStorage > Shared > Config` | ModuleScript |
| `src/server/GameMode/init.server.luau` | `ServerScriptService > GameMode` | Script |
| `src/server/GameMode/Arena.luau` | `ServerScriptService > GameMode > Arena` | ModuleScript |
| `src/server/GameMode/Coins.luau` | `ServerScriptService > GameMode > Coins` | ModuleScript |
| `src/client/HUD.client.luau` | `StarterPlayer > StarterPlayerScripts > HUD` | LocalScript |

## Installazione

**Con Rojo** (consigliato):

```sh
rojo serve
```

poi in Roblox Studio apri il plugin Rojo e premi *Connect*.

**A mano**: in Roblox Studio crea gli oggetti indicati nella tabella qui sopra (rispettando
nome e tipo) e incolla il contenuto di ciascun file. `Arena` e `Coins` devono essere figli
dello Script `GameMode`.

Premi **Play** per provarla.

## Personalizzazione

Tutte le impostazioni sono in `src/shared/Config.luau`: durata dei round, numero minimo di
giocatori, frequenza e valore delle monete, dimensione e posizione dell'arena, numero di
pilastri. Per un server pubblico conviene impostare `MIN_PLAYERS = 2` o più.
