# Pet e uova di Climb & Steal Eggs

Questo pacchetto contiene i **47 pet** e le **10 uova** del gioco Roblox *Climb & Steal Eggs*
(luogo `126700834809859`), pronti per essere riusati in un altro progetto. Dentro ci sono:
- i modelli 3D;
- gli id degli asset già caricati su Roblox;
- i dati di gioco;
- il codice Roblox che li carica, li scala, applica mutazioni ed effetti e li anima;
- gli script Blender che li generano.

Stile: giocattoli da collezione in vinile lucido, colori saturi, con un tocco leggero di "toy
horror": ghigni con dentini aguzzi, cuciture, toppe, chiavi a molla.

## In breve

- `anteprima_pet.jpg` e `anteprima_uova.jpg` mostrano tutti i modelli divisi per rarità.
- Ogni modello è già su Roblox come asset **Model**: l'id è in `catalog.json`
  (`model.robloxAssetId`) e in `roblox/PetAssets.luau`.
- Se l'esperienza appartiene allo **stesso account Roblox** che ha caricato gli asset (utente
  `118377242`), i modelli si caricano con `InsertService:LoadAsset(id)`: vedi il metodo A.
- Altrimenti si importano gli **FBX** di `models/` (metodo B).
- Le MeshPart non hanno texture. Colore, materiale e posizione di ogni parte vanno applicati dai dati
  del modello (il file JSON o `PetAssets.luau`).

## Contenuto

```
README.md               questa guida
catalog.json            dati di gioco e parti di ogni modello (descritto più sotto)
anteprima_pet.jpg       i 47 pet divisi per rarità, con nome italiano e id
anteprima_uova.jpg      le 10 uova
models/pets/<Id>/       <Id>.fbx (mesh), <Id>.json (parti), <Id>.jpg (anteprima)
models/eggs/<Id>/       come sopra, per le uova (EggCommon ... EggUltra, EggPrimal)
roblox/PetAssets.luau   manifest Luau: id dell'asset e proprietà delle parti di ogni modello
roblox/reference/       codice del gioco originale, da cui copiare o prendere spunto:
  AssetService.luau       carica gli asset e costruisce i modelli (funzione build)
  Visuals.luau            MakePet/MakeEgg: scala, mutazioni, particelle di pet e uova
  Config/Pets.luau        elenco dei pet (rarità, guadagno, altezza, zona)
  Config/Rarities.luau    rarità (colori, tempi di schiusa)
  Config/Variants.luau    mutazioni e taglie
source/art/             script Blender (SDF) che generano i modelli, con guida allo stile
source/tools/           caricamento su Roblox via Open Cloud (upload_assets.py, rbxcloud.py)
```

## Convenzioni dei modelli

- **Spazio del modello** (coordinate Roblox, le stesse del JSON e del manifest):
  - Y verso l'alto, i piedi a y = 0, centrato su x = 0.
  - Il modello **guarda verso -Z**, cioè la LookVector del suo perno.
- **Dimensioni**: un modello è alto circa 3-4,6 unità (`size` = [x, y, z]).
  - In gioco ogni pet viene scalato all'altezza `height` del catalogo (in stud): `model:ScaleTo(height / size[2])`.
  - La taglia moltiplica l'altezza: Mini ×0,7, Normale ×1, Gigante ×1,5.
- **Parti**: ogni parte è una MeshPart con un solo colore e un solo materiale. Il nome della parte è
  lo stesso nell'FBX e nel JSON. Per ogni parte ci sono:
  - `role`: ruolo della parte (elenco qui sotto);
  - `color`: RGB 0-255;
  - `material`: nome di `Enum.Material`;
  - `transparency` e `reflectance`, se presenti;
  - `center`: centro della parte nello spazio del modello;
  - `group` e `pivot`: solo per le parti animate.
- **Ruoli**:
  - `skin`: colore principale, sempre la prima parte;
  - `detail`: colori secondari e accessori;
  - `eye`: occhi, bocca e narici scuri;
  - `shine`: riflessi bianchi;
  - `glow`: parti luminose, sempre `Neon`.
- **Triangoli**: al massimo circa 16.000 per modello.

## Usarli in Roblox

### A) Stesso proprietario: InsertService

`InsertService:LoadAsset` funziona solo sul server (o in Studio) e solo per asset dello stesso
proprietario dell'esperienza. Si caricano una volta all'avvio, si puliscono e si clonano quando
servono. Versione ridotta di `build` in `roblox/reference/AssetService.luau`:

```lua
local InsertService = game:GetService("InsertService")
local PetAssets = require(path.to.PetAssets) -- roblox/PetAssets.luau

local function loadModel(id: string): Model
	local info = PetAssets[id]
	local loaded = InsertService:LoadAsset(info.asset)
	local byName = {}
	for _, p in info.parts do
		byName[p.name] = p
	end
	local model = Instance.new("Model")
	model.Name = id
	for _, d in loaded:GetDescendants() do
		if d:IsA("MeshPart") then
			local p = byName[d.Name]
			if p then
				-- posizione dal manifest: non dipende da dove l'importatore ha messo la parte
				if p.center then
					d.CFrame = CFrame.new(p.center[1], p.center[2], p.center[3]) * d.CFrame.Rotation
				end
				d.Color = Color3.fromRGB(p.color[1], p.color[2], p.color[3])
				d.Material = (Enum.Material :: any)[p.material]
				d.Transparency = p.transparency or 0
				d.Reflectance = p.reflectance or 0
				d:SetAttribute("Role", p.role)
				d:SetAttribute("BaseColor", d.Color)
				if p.group then
					d:SetAttribute("Group", p.group)
					d:SetAttribute("Pivot", Vector3.new(p.pivot[1], p.pivot[2], p.pivot[3]))
				end
			end
			d.Anchored = true
			d.CanCollide = false
			d.Parent = model
		end
	end
	loaded:Destroy()
	model.WorldPivot = CFrame.new() -- perno ai piedi, all'origine
	model:SetAttribute("Height", info.size[2])
	return model
end
```

Il gioco originale aggiunge anche una parte `Root` invisibile come `PrimaryPart` all'origine.

### B) Altro proprietario: ricaricare gli FBX

- **Studio**: importare `models/.../<Id>.fbx` con il 3D Importer. Le MeshPart prendono i nomi delle
  parti; poi si applicano posizione, colore e materiale dal `<Id>.json` come nel codice sopra.
- **Open Cloud**: `source/tools/upload_assets.py` carica gli FBX come asset Model e rigenera un
  manifest Luau con i nuovi id. Prima di usarlo:
  - copiare i modelli in `art/out/pet/<Id>/` e `art/out/egg/<Id>/`;
  - cambiare `UNIVERSE_ID`, `PLACE_ID` e `CREATOR_USER_ID` in `rbxcloud.py`;
  - impostare `ROBLOX_API_KEY` con una chiave che possa scrivere asset.

## Scala, mutazioni, effetti e animazioni (come nel gioco originale)

Il codice di riferimento è in `roblox/reference/Visuals.luau`.

- **Scala** (`MakePet`): altezza del pet × taglia, e `ScaleTo` sul modello.
- **Mutazioni** (`ApplyMutation`): moltiplicatori e probabilità sono in `catalog.json` → `mutations`.
  Le parti `eye` e `shine` non cambiano mai; le `glow` restano Neon.
  - **Gold** (×2): colore oro e materiale Foil.
  - **Diamond** (×3): azzurro chiaro, Glass, trasparenza 0,08.
  - **Rainbow** (×5): i colori cambiano nel tempo, animati dal client su tutti i modelli con il tag `RainbowPet`.
  - **Cosmic** (×10): `skin` viola notte, le altre parti Neon lilla, con particelle e luce.
- **Effetti dei pet** (`PetEffects`, solo Ultra e Primordiali): `ParticleEmitter` sulle parti
  chiamate `Aura`, `Mane`, `Flames`, `Rage`, `Venom`, `Frost` e `Shadow`.
  - Questi nomi sono riservati: non usarli per altre parti.
  - I Primordiali hanno il 60% delle particelle e niente luci.
  - Le parti di ogni pet sono in `catalog.json` → `model.effectParts`.
- **Effetti delle uova** (`EggEffects`):
  - particelle dalla rarità Rara in su, luce dalla Epica;
  - la Mitica ha le fiamme, la Segreta scintille viola-turchesi, la Primordiale le braci;
  - la Ultra ha fiamme e una colonna di luce verso il cielo.
- **Animazione** (sul client): il pet fa un piccolo saltello e ondeggia. Le parti con `group` e
  `pivot` (ali, code) oscillano attorno all'asse avanti-dietro nel punto `pivot`:
  - `pivot` è in coordinate del modello **non scalato**: va moltiplicato per `model:GetScale()`;
  - ampiezza 16° (28° se il pet vola, 10° per i giganti Ultra);
  - i gruppi che finiscono con `L` vanno nel verso opposto.

  ```lua
  local flap = math.sin(t * 9) * math.rad(16) * (if string.sub(group, -1) == "L" then -1 else 1)
  part.CFrame = root * pivotCF * CFrame.Angles(0, 0, flap) * pivotCF:Inverse() * offset
  ```

## catalog.json

- `rarities`: id, ordine, nome (it/en), colori `color`/`colorDark` (RGB), `hatchSeconds` (secondi
  di schiusa), `hatchSecondsByZone` (Primordiali), `carrySpeedMult` (velocità mentre lo si porta).
- `mutations`, `sizes`: id, moltiplicatore del guadagno, probabilità, colore o scala.
- `zones`: le zone del gioco originale. I Primordiali sono due per zona e la zona decide quale nasce.
- `pets`: per ogni pet:
  - id e nome (it/en);
  - `rarity`, `incomePerSecond` (monete al secondo), `chanceWeight` (peso dentro la rarità);
  - `height` (altezza in gioco, in stud);
  - `flying` (fluttua), `giant` (Ultra, alto 10 volte gli altri), `zone`;
  - `model`, cioè `robloxAssetId`, `size`, `parts` ed `effectParts`;
  - `files` (percorsi nel pacchetto).
- `eggs`: id (`Egg<Rarità>`), rarità, nome, `model` e `files`.

I numeri di gioco (guadagni, probabilità, tempi) sono bilanciati per *Climb & Steal Eggs*:
in un altro gioco vanno adattati.

## Rigenerare o modificare i modelli

I modelli sono generati con funzioni di distanza con segno (SDF) in Python con Blender come
libreria (`bpy`). Ogni parte è una forma liscia che diventa una MeshPart.

```bash
pip install bpy==5.2.2 numpy requests scikit-image trimesh pillow   # Python 3.13
cd source/art
VIEWS=3q,front RES=600 python pets/chick.py          # un pet  -> art/out/pet/Chick/
python eggs/eggs.py Common Primal                    # uova    -> art/out/egg/EggCommon/ ...
```

Lo script di un pet è `pets/<nome_snake_case>.py` e la libreria è in `lib/` (`sdf.py` forme,
`toy.py` modello e parti, `mesher.py`, `render.py`). Convenzioni, budget e guida allo stile sono in
`source/art/README.md`.

## Elenco dei modelli

{{MODELS_TABLE}}
