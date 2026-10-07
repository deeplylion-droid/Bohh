-- Impostazioni di "The Rake: Caccia nei Boschi". Modifica questi valori per bilanciare il gioco.
-- Il modulo è condiviso: lo leggono sia il server sia i client.
return {
	-- Giocatori necessari per iniziare (il gioco è pensato per 1-8: imposta il massimo in Game Settings)
	MIN_PLAYERS = 1,

	-- Durate in secondi
	BRIEFING = 30,
	NIGHT_DURATION = 600, -- la notte va dalle 20:00 alle 06:00 in questo tempo reale
	DEBRIEF = 15,

	NIGHT_START_HOUR = 20,
	NIGHT_HOURS = 10,

	-- "Ricognizione", "Caccia", "Sopravvivenza", "Reperto" oppure nil per sceglierlo a caso
	FORCED_OBJECTIVE = nil,
	RECON_CAMERAS = 4, -- telecamere attive richieste dall'obiettivo Ricognizione
	RECON_EVIDENCE = 3, -- prove richieste dall'obiettivo Ricognizione

	MAP = {
		SIZE = 800, -- lato del bosco in stud, centrato nell'origine
		PATH_WIDTH = 8,
		STATION_RADIUS = 30, -- area sicura (finché la creatura non è Aggressiva)
		-- Punti di interesse fissi; il primo è la Ranger Station (spawn, sala di controllo, laboratorio)
		POIS = {
			{ name = "Ranger Station", pos = Vector3.new(0, 0, 0), radius = 34 },
			{ name = "Torre di avvistamento", pos = Vector3.new(210, 0, -230), radius = 18 },
			{ name = "Campeggio abbandonato", pos = Vector3.new(-230, 0, -210), radius = 36 },
			{ name = "Lago", pos = Vector3.new(-185, 0, 160), radius = 16 },
			{ name = "Capanno", pos = Vector3.new(-40, 0, 300), radius = 18 },
			{ name = "Miniera", pos = Vector3.new(250, 0, 230), radius = 45 },
		},
		LAKE = { center = Vector3.new(-235, 0, 205), radius = 55 },
		-- Sentieri come coppie di indici di POIS (la stazione è collegata a tutti)
		PATHS = { { 1, 2 }, { 1, 3 }, { 1, 4 }, { 1, 5 }, { 1, 6 }, { 2, 6 }, { 3, 4 }, { 4, 5 } },
	},

	-- Meteo estratto a ogni notte (weight = probabilità relativa, density = densità dell'atmosfera)
	WEATHER = {
		{ name = "Sereno", weight = 4, density = 0.36, cameraNoise = 0 },
		{ name = "Nebbia", weight = 3, density = 0.58, cameraNoise = 0.25 },
		{ name = "Pioggia", weight = 2, density = 0.46, cameraNoise = 0.4 },
	},

	-- Quantità di vegetazione e oggetti generati a ogni partita (abbassale se il gioco va a scatti)
	VEGETATION = {
		TREES = 560,
		BUSHES = 520,
		FERNS = 650,
		ROCKS = 170,
		BOULDERS = 34,
		LOGS = 46,
		STUMPS = 55,
		MUSHROOMS = 60,
		REEDS = 140,
		EFFIGIES = 14, -- figure di rami appese: inquietanti
	},

	PLAYER = {
		WALK_SPEED = 12,
		SPRINT_SPEED = 20,
		STAMINA_DRAIN = 22, -- al secondo mentre corri (stamina massima 100)
		STAMINA_REGEN = 12,
		HEALTH = 100,
		HEALTH_REGEN = 1.5, -- salute al secondo recuperata...
		REGEN_DELAY = 12, -- ...dopo questi secondi senza essere colpiti
		REVIVE_HEALTH = 40,
		DOWNED_TIME = 30, -- secondi per essere rianimati prima di essere eliminati
		REVIVE_TIME = 3,
		FEAR_SLOWDOWN = 0.7, -- moltiplicatore di velocità con la Paura al massimo
	},

	EQUIPMENT = {
		DARTS = 6,
		DART_RANGE = 160,
		DART_COOLDOWN = 1.1, -- tempo per riarmare l'otturatore
		DART_SPEED = 260, -- velocità del dardo in volo (stud/s)
		TORCH_BATTERY = 180, -- secondi di luce
		NIGHT_VISION_BATTERY = 60,
		CAMERA_KITS = { Fissa = 2, IR = 1, Motorizzata = 1, Trappola = 1 },
	},

	CAMERAS = {
		TYPES = { "Fissa", "IR", "Motorizzata", "Trappola" },
		BATTERY = 300,
		VIEW_RANGE = 70,
		FOV = 70, -- gradi
		IR_RANGE_BONUS = 1.4, -- tutte le camere vedono al buio; il modello IR ha più portata
		TRAP_RANGE = 35,
		TRAP_COOLDOWN = 20,
		TRAP_TRACKING = 10,
		DISTORT_RANGE = 45, -- sotto questa distanza dalla creatura il feed si corrompe
		COVERAGE_CELL = 25,
	},

	EVIDENCE = {
		START_COUNT = 8,
		MAX_ACTIVE = 16,
		DROP_INTERVAL = 25, -- ogni quanto la creatura lascia una traccia
		TRACKING = { Impronte = 8, Graffi = 8, Peli = 6, Sangue = 6, Carcassa = 12 },
		NEEDS_LAB = { Peli = true, Sangue = true }, -- vanno analizzati alla Ranger Station
		LAB_MULTIPLIER = 3,
		LAB_TIME = 12,
		FAKE_CHANCE = 0.2, -- probabilità che una traccia sia un depistaggio
		SIGHTING_RATE = 3, -- tracciamento al secondo mentre una camera inquadra la creatura
		REVEAL = { ZONE = 30, AREA = 65, EXACT = 100 }, -- soglie della barra di Tracciamento
	},

	RAKE = {
		WALK_SPEED = 12,
		STALK_SPEED = 16,
		CHASE_SPEED = 27, -- più veloce di un giocatore che corre (20): la luce e i compagni sono la difesa
		ATTACK_RANGE = 6.5,
		ATTACK_PAUSE = 1.0, -- resta sopra la vittima (jumpscare) prima di fuggire
		DAMAGE = { 16, 22 }, -- salute tolta a ogni attacco: servono 5-6 attacchi per finire a terra
		AGGRESSION_PER_SECOND = 0.2, -- crescita di base, aumenta col passare della notte
		ACTION_INTERVAL = { 16, 6 }, -- secondi tra un'azione e l'altra (aggressività bassa -> alta)
		REVEAL_TIME = { 2.5, 4 }, -- secondi in cui si mostra immobile prima di sparire
		CHARGE_TIMEOUT = 9,
		LIGHT_RANGE = 40, -- una torcia puntata da questa distanza la mette in fuga
		LIGHT_ANGLE = 30,
		LIGHT_TO_FLEE = 1.2, -- secondi di luce diretta necessari
		FLEE_TIME = { 8, 14 },
		DARTS_TO_KNOCKOUT = 4,
		SEDATION_DECAY = 0.01, -- dardi "smaltiti" al secondo
		KNOCKOUT_TIME = 25,
		CAPTURE_TIME = 5,
	},

	XP = {
		EVIDENCE = 15,
		CAMERA_SIGHTING = 10,
		REVIVE = 30,
		CAPTURE = 150,
		SURVIVE = 60,
		WIN = 100,
		LOSS_MULTIPLIER = 0.5, -- XP dimezzati in caso di sconfitta
	},

	RANKS = {
		{ name = "Novizio", xp = 0 },
		{ name = "Ricercatore", xp = 500 },
		{ name = "Cacciatore", xp = 1500 },
		{ name = "Veterano", xp = 4000 },
		{ name = "Leggenda", xp = 10000 },
	},
}
