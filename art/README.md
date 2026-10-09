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

Giocattolo in vinile morbido e lucido, colori saturi e allegri, forme tonde e "paffute":
testa grande (circa il 45-50% dell'altezza), corpo a goccia, zampe corte, **occhi grandi e
lucidi** (ellissoidi scuri appoggiati sulla testa con `Frame(...).place`) con **due riflessi
bianchi** sullo stesso lato in entrambi gli occhi, guance rosa (`stick`), bocca sorridente
disegnata sulla superficie (`project_curve` + `tube`). Silhouette leggibile da lontano: un
elemento distintivo grande per ogni pet (orecchie, corna, coda, criniera, guscio, accessorio).
I pet piu' rari sono piu' elaborati, con parti `glow` e accessori. Le creature "meme" (Mitici,
Divini, Segreti) sono personaggi originali a tema cibo/oggetti italiani: nessun personaggio
esistente.

## Strumenti principali (`lib/sdf.py`)

- Primitive: `sphere`, `ellipsoid`, `box(round=)`, `capsule`, `round_cone`, `capped_cone`,
  `cylinder`, `torus`, `egg`, `prism` (poligono estruso), `octahedron`, `tube(punti, raggi)`,
  `bezier(p0, p1, p2, p3, n)`, `revolve`.
- Operazioni: `union(..., k=)` (unione morbida), `a.subtract(b, k=)`, `a.intersect(b)`,
  `.translate`, `.rot(rx, ry, rz)`, `.scale`, `.offset(d)` (gonfia/sgonfia),
  `.shell(t)`, `.mirrored()` (copia speculare su x), `.symmetric()`, `.warp(fn)`.
- Disegni sulla superficie: `core.offset(0.02).intersect(regione)` crea una "vernice" (pancia,
  macchie, strisce) che segue la forma; `Frame(base, origine, direzione, sink)` e `stick(...)`
  appoggiano una forma sulla superficie; `project_curve` proietta una curva sulla superficie.
