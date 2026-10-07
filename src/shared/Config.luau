-- Impostazioni della modalità "Coin Rush". Modifica questi valori per bilanciare il gioco.
return {
	-- Giocatori necessari per avviare un round (metti 2+ per un server pubblico)
	MIN_PLAYERS = 1,

	-- Durate in secondi
	INTERMISSION = 15,
	ROUND_DURATION = 90,
	RESULTS_DURATION = 6,

	-- Monete
	COIN_SPAWN_INTERVAL = 1.2,
	MAX_COINS = 25,
	COIN_VALUE = 1,

	-- Arena (generata automaticamente in Workspace se non esiste)
	ARENA_CENTER = Vector3.new(0, 200, 0),
	ARENA_SIZE = 120,
	PILLAR_COUNT = 14,

	-- Sotto questa distanza dal pavimento dell'arena il giocatore è eliminato
	FALL_LIMIT = 25,
}
