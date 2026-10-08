--!strict
-- Impostazioni generali di gioco.

local Game = {}

Game.Name = "Climb & Steal Eggs"
Game.PlotCount = 8
Game.StartingCoins = 100
Game.CreatorUserId = 118377242 -- proprietario: ha accesso al pannello admin
Game.ExtraAdmins = {} :: { number }
Game.GroupId = 0 -- gruppo per il premio "unisciti al gruppo" (0 = disattivato)
Game.GroupReward = 2500

-- Raccolta e trasporto
Game.PickupHold = 0.25
Game.HatchHold = 0.4
Game.SellHold = 1.0
Game.StealHold = 2.0
Game.DroppedEggLifetime = 25 -- secondi prima che un uovo caduto torni al suo nido
Game.CarrySpacing = 2.6 -- distanza verticale fra uova impilate sopra la testa

-- Pet e monete
Game.IncomeTick = 1 -- ogni quanto (s) maturano le monete sui piedistalli
Game.OfflineRate = 0.25 -- quota del guadagno al secondo accreditata da offline
Game.OfflineRateVIP = 0.5
Game.OfflineMaxSeconds = 4 * 3600
Game.FriendBonusEach = 0.1
Game.FriendBonusMax = 0.4
Game.VIPIncomeBonus = 0.2
Game.IndexRowBonus = 0.05 -- bonus permanente per ogni rarita' completata nell'album

-- Furti e difese
Game.StealSpeedMult = 0.8 -- moltiplicatore extra di velocita' per chi trasporta refurtiva
Game.BarrierCooldown = 45
Game.AlarmCooldown = 20
Game.StealProtectAfterJoin = 60 -- secondi di protezione dai furti dopo l'ingresso

-- Schiaffi
Game.SlapRagdoll = 1.2
Game.SpawnProtection = 4

-- Valanga
Game.AvalancheInterval = 150
Game.AvalancheWarning = 15
Game.AvalancheDuration = 26

-- Eventi
Game.EventMinGap = 12 * 60
Game.EventMaxGap = 18 * 60
Game.EventFirstDelay = 5 * 60

-- Tutorial: il nuovo giocatore riceve un uovo comune gia' in incubazione
Game.StarterEggHatch = 10

return Game
