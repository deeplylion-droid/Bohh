-- Costruisce il mondo all'avvio: luce, terreno della montagna, vetta, rifugi, nuvole e decorazioni.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Signal = require(ReplicatedStorage.Shared.Util.Signal)
local Terrain = require(script.Parent.Parent.World.Terrain)
local WorldLighting = require(script.Parent.Parent.World.Lighting)
local Scenery = require(script.Parent.Parent.World.Scenery)

local MapService = {}

MapService.Ready = false
MapService.Built = Signal.new()
MapService.Folder = nil :: Folder?

local S

function MapService.Init(services)
	S = services
	local folder = Instance.new("Folder")
	folder.Name = "Map"
	folder.Parent = workspace
	MapService.Folder = folder
end

function MapService.Start()
	local t0 = os.clock()
	WorldLighting.Apply()
	local ok, err = pcall(Terrain.Build)
	if not ok then
		warn(`[MapService] terreno: {err}`)
	end
	local folder = MapService.Folder :: Folder
	local assets = {
		Clone = function(category, name)
			return S.AssetService.Clone(category, name)
		end,
	}
	Scenery.Summit(folder, assets)
	Scenery.Shelters(folder)
	Scenery.CloudSea(folder)
	Scenery.Decor(folder, assets, Terrain.HeightAt)
	MapService.Ready = true
	workspace:SetAttribute("MapBuildTime", os.clock() - t0)
	MapService.Built:Fire()
end

function MapService.WaitReady()
	if not MapService.Ready then
		MapService.Built:Wait()
	end
end

-- Altezza del terreno (per posizionare oggetti senza raycast)
function MapService.HeightAt(x: number, z: number): number
	Terrain.Prepare()
	local h = Terrain.HeightAt(x, z)
	return h
end

return MapService
