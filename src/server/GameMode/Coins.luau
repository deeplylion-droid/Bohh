-- Genera le monete nell'arena e notifica quando un giocatore ne raccoglie una.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Arena = require(script.Parent.Arena)

local Coins = {}
Coins.__index = Coins

export type Coins = typeof(setmetatable(
	{} :: { arena: Model, folder: Folder, onCollected: (Player) -> boolean },
	Coins
))

-- onCollected riceve il giocatore e restituisce true se la moneta va assegnata.
function Coins.new(arena: Model, onCollected: (Player) -> boolean): Coins
	local folder = Instance.new("Folder")
	folder.Name = "CoinRushCoins"
	folder.Parent = workspace
	return setmetatable({ arena = arena, folder = folder, onCollected = onCollected }, Coins)
end

function Coins.spawn(self: Coins)
	if #self.folder:GetChildren() >= Config.MAX_COINS then
		return
	end

	local coin = Instance.new("Part")
	coin.Name = "Coin"
	coin.Shape = Enum.PartType.Cylinder
	coin.Size = Vector3.new(0.6, 3, 3)
	coin.Color = Color3.fromRGB(255, 200, 40)
	coin.Material = Enum.Material.Neon
	coin.Anchored = true
	coin.CanCollide = false
	coin.Position = Arena.randomSurfacePoint(self.arena, 2.5)

	local taken = false
	coin.Touched:Connect(function(hit)
		if taken then
			return
		end
		local player = Players:GetPlayerFromCharacter(hit.Parent)
		if player and self.onCollected(player) then
			taken = true
			coin:Destroy()
		end
	end)

	coin.Parent = self.folder
end

function Coins.destroy(self: Coins)
	self.folder:Destroy()
end

return Coins
