# Modelli 3D di Climb & Steal Eggs

Tutti i modelli (pet, uova, oggetti dello scenario) sono generati da script Python con
funzioni di distanza con segno (SDF): ogni parte del modello e' una forma liscia che diventa
una MeshPart di Roblox con un solo colore e materiale. Le mutazioni (Oro, Diamante,
Arcobaleno, Cosmico) ricolorano le parti in base al loro *ruolo*, quindi le texture non servono.

## Uso

```bash
tools/setup.sh                      # una volta: Blender (bpy), numpy, scikit-image...
cd art
VIEWS=3q,front RES=600 ../.tools/venv/bin/python pets/chick.py
```

Uscita in `art/out/<tipo>/<Nome>/`: `Nome.fbx` (da caricare su Roblox), `Nome.json`
(colori, materiali, ruoli, centri e misure delle parti in coordinate Roblox), `Nome.blend` e i
render di anteprima `Nome_3q.png`, `Nome_front.png` (viste: `3q`, `front`, `side`, `back`, `top`).

## Convenzioni

- **Assi (Blender)**: Z in alto, il modello **guarda verso -Y**, i piedi poggiano su z = 0,
  centrato su x = 0. Il pet ha un'altezza di circa 3 unita' (l'altezza vera in gioco la decide
  `Config/Pets.luau`: il modello viene scalato).
- **Nome del modello** = id del pet in `src/shared/Config/Pets.luau` (es. `Model("FoxKit", "pet")`),
  uno script per modello in `art/pets/<nome_snake_case>.py`.
- **Ruoli delle parti** (`role=`):
  - `skin`: colore principale del corpo (una sola parte grande, la prima);
  - `detail`: colori secondari (pancia, orecchie, zampe, accessori);
  - `eye`: occhi scuri; `shine`: riflessi bianchi negli occhi (le mutazioni non li toccano);
  - `glow`: parti luminose, sempre con `material="Neon"`.
- **Materiali**: nomi dei materiali Roblox (`SmoothPlastic` predefinito, `Neon`, `Glass`, `Ice`,
  `Foil`, `Metal`, `Wood`, `Fabric`...). Usare `Glass`/`Neon` con misura: in gioco non c'e' rifrazione.
- **Animazioni**: ali, pinne e orecchie possono avere `group="WingL"`/`"WingR"` (o `EarL`/`EarR`,
  il gruppo che finisce con `L` sbatte nel verso opposto) e `pivot=(x, y, z)` nel punto
  dell'attaccatura (coordinate Blender). Il gioco le fa oscillare attorno all'asse avanti-dietro.
- **Triangoli**: al massimo ~16.000 per modello e 8.000 per parte (`tris=`); occhi, riflessi e
  piccoli dettagli 400-1.000. Ogni parte diventa una MeshPart: meglio 8-16 parti che 40.
- Dettagli molto piccoli (riflessi, bocca, narici) con `voxel=0.01`-`0.015`.

## Stile

Giocattolo da collezione lucido e ben rifinito, ma con **personalita'** e un tocco leggero
(circa 20%) di "toy horror" alla Poppy Playtime: giocattoli che sembrano prendere vita di notte.
Non fanno paura, ma non sono nemmeno solo "dolci":

- **Espressione**: ghigno largo e furbo (anche asimmetrico) con una fila di **dentini aguzzi**
  bianchi su bocca scura, oppure sorriso cucito; sopracciglia spesse e inclinate; palpebra
  superiore che copre in parte l'occhio (sguardo sornione) o pupille piu' piccole con il bianco
  dell'occhio visibile; ogni tanto **occhi a bottone** cuciti (con il filo a X) o occhi diversi.
- **Dettagli da peluche/giocattolo**: cuciture visibili (file di trattini sulla superficie),
  toppe cucite di un altro colore, bottoni; per gli animali di peluche il corpo puo' usare il
  materiale `Fabric`.
- **Proporzioni**: testa ancora grande ma meno "neonato"; braccia e gambe un po' piu' lunghe,
  mani piu' grandi con dita tozze; posture con carattere (spalle curve, testa inclinata).
- **Colori**: saturi e con piu' contrasto, accenti scuri (viola, blu notte, bordeaux), meno pastello.
- Ogni pet ha un tratto di carattere riconoscibile (furbo, sbruffone, inquietante-tenero,
  scontroso...). Le creature "meme" (Mitici, Divini, Segreti) restano personaggi originali a
  tema cibo/oggetti italiani: nessun personaggio esistente, nemmeno di Poppy Playtime.

Ambiente: niente forme "a caramella". Rocce **spigolose e taglienti** (sfaccettature piatte,
punte, crepe), colori naturali e meno saturi; alberi e piante stilizzati ma credibili.

## Strumenti principali (`lib/sdf.py`)

- Primitive: `sphere`, `ellipsoid`, `box(round=)`, `capsule`, `round_cone`, `capped_cone`,
  `cylinder`, `torus`, `egg`, `prism` (poligono estruso), `octahedron`, `tube(punti, raggi)`,
  `bezier(p0, p1, p2, p3, n)`, `revolve`.
- Nota: `cylinder(..., round=r)` arrotonda i bordi allungando il cilindro di `r` a ogni estremita'.
- Operazioni: `union(..., k=)` (unione morbida), `a.subtract(b, k=)`, `a.intersect(b)`,
  `.translate`, `.rot(rx, ry, rz)`, `.scale`, `.offset(d)` (gonfia/sgonfia),
  `.shell(t)`, `.mirrored()` (copia speculare su x), `.symmetric()`, `.warp(fn)`.
- Disegni sulla superficie: `core.offset(0.02).subtract(core.offset(-0.06)).intersect(regione)`
  crea una "vernice" (pancia, macchie, strisce) che segue la forma (il guscio sottile evita grandi
  superfici interne nascoste che sprecano triangoli e rovinano la decimazione); `Frame(base, origine, direzione, sink)` e `stick(...)`
  appoggiano una forma sulla superficie; `project_curve` proietta una curva sulla superficie.
