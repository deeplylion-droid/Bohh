-- Avvio dei servizi del server. Ogni servizio espone Init(S) (nessuna attesa) e Start().
-- S e' il registro condiviso: S.NomeServizio da' accesso agli altri servizi senza require ciclici.

local Net = require(game:GetService("ReplicatedStorage").Shared.Net)

local Boot = {}
Boot.Services = nil :: any

local ORDER = {
	"DataService",
	"StateService",
	"AnalyticsService",
	"AssetService",
	"MapService",
	"PlotService",
	"CharacterService",
	"RagdollService",
	"CarryService",
	"NestService",
	"HatchService",
	"PetService",
	"StealService",
	"DefenseService",
	"CombatService",
	"UpgradeService",
	"ObstacleService",
	"AvalancheService",
	"GuardianService",
	"EventService",
	"MonetizationService",
	"RewardService",
	"IndexService",
	"LeaderboardService",
	"TutorialService",
	"AdminService",
	"ChatService",
}

local started = false

-- options.test = true: nessun personaggio/ciclo automatico (per i test in sessione di esecuzione)
function Boot.Start(options: { test: boolean? }?)
	if started then
		return Boot.Services
	end
	started = true
	Net.Setup()
	local S = { Options = options or {} }
	Boot.Services = S
	local folder = script.Parent.Services
	for _, name in ORDER do
		local module = folder:FindFirstChild(name)
		assert(module, `Servizio mancante: {name}`)
		S[name] = require(module)
	end
	for _, name in ORDER do
		if S[name].Init then
			S[name].Init(S)
		end
	end
	for _, name in ORDER do
		if S[name].Start then
			local ok, err = pcall(S[name].Start)
			if not ok then
				warn(`[Boot] Errore all'avvio di {name}: {err}`)
			end
		end
	end
	workspace:SetAttribute("ServerReady", true)
	return S
end

return Boot
