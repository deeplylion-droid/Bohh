-- Difese del lotto: barriera laser, allarme per gli intrusi, trappole.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Combat = require(ReplicatedStorage.Shared.Config.Combat)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Net = require(ReplicatedStorage.Shared.Net)
local Upgrades = require(ReplicatedStorage.Shared.Config.Upgrades)

local DefenseService = {}

local S
local alarmSeen: { [string]: number } = {} -- "ownerId:intruderId" -> ultimo avviso
local trapModels: { [number]: { [string]: Model } } = {} -- [plotIndex][slot]

function DefenseService.Init(services)
	S = services
end

---------------------------------------------------------------------------------------------
-- Barriera
---------------------------------------------------------------------------------------------
local function setBarrier(plot, on: boolean)
	local b = plot.gateBarrier
	b.CanCollide = on
	b.Transparency = if on then 0.35 else 1
	plot.model:SetAttribute("BarrierOn", on)
end

function DefenseService.ActivateBarrier(player: Player)
	local plot = S.PlotService.Get(player)
	local data = S.DataService.Get(player)
	if not plot or not data then
		return
	end
	local now = workspace:GetServerTimeNow()
	if (player:GetAttribute("BarrierReadyAt") or 0) > now or plot.model:GetAttribute("BarrierOn") then
		return
	end
	local super = S.MonetizationService.HasPass(player, "SuperBarrier")
	local duration = Upgrades.BarrierDuration(data.Upgrades.Barrier, super)
	local cooldown = GameConfig.BarrierCooldown * (if super then 0.5 else 1)
	setBarrier(plot, true)
	plot.model:SetAttribute("BarrierUntil", now + duration)
	player:SetAttribute("BarrierReadyAt", now + duration + cooldown)
	S.StateService.Notify(player, "BarrierOn", { t = math.floor(duration) .. "s" }, "Good")
	S.StateService.Effect(nil, "Barrier", { plot = plot.index, on = true })
	-- gli intrusi vengono sbalzati fuori e perdono la refurtiva
	for _, other in Players:GetPlayers() do
		if other ~= player then
			local hrp = S.CharacterService.Root(other)
			if hrp and S.PlotService.Contains(plot, hrp.Position) then
				S.CarryService.DropAll(other, "Trap")
				local out = plot.cframe * CFrame.new(0, 4, -MapLayout.PlotSize.Z / 2 - 8)
				other.Character:PivotTo(CFrame.lookAt(out.Position, out.Position + plot.cframe.LookVector))
				S.RagdollService.Ragdoll(other, 1, plot.cframe.LookVector * 40 + Vector3.new(0, 30, 0))
			end
		end
	end
	task.delay(duration, function()
		if plot.owner == player then
			setBarrier(plot, false)
			S.StateService.Effect(nil, "Barrier", { plot = plot.index, on = false })
		end
	end)
end

---------------------------------------------------------------------------------------------
-- Trappole
---------------------------------------------------------------------------------------------
local function trapVisual(plot, slot: string, trapId: string?)
	trapModels[plot.index] = trapModels[plot.index] or {}
	local old = trapModels[plot.index][slot]
	if old then
		old:Destroy()
		trapModels[plot.index][slot] = nil
	end
	if not trapId then
		return
	end
	local spot = plot.traps[tonumber(slot) or 0]
	if not spot then
		return
	end
	local model = S.AssetService.Clone("Props", "Trap" .. trapId)
	if not model then
		model = Instance.new("Model")
		local p = Instance.new("Part")
		p.Name = "Body"
		p.Shape = Enum.PartType.Cylinder
		p.Size = Vector3.new(0.5, 3.4, 3.4)
		p.Color = Combat.Traps[trapId].color
		p.Material = Enum.Material.SmoothPlastic
		p.Anchored = true
		p.CanCollide = false
		p.CFrame = CFrame.new(0, 0.25, 0) * CFrame.Angles(0, 0, math.rad(90))
		p.Parent = model
		model.PrimaryPart = p
		model.WorldPivot = CFrame.new()
	end
	model.Name = "Trap" .. slot
	model:PivotTo(CFrame.new(spot.Position) * (plot.cframe - plot.cframe.Position))
	model:SetAttribute("TrapId", trapId)
	model.Parent = plot.model
	trapModels[plot.index][slot] = model
end

local function buyTrap(player: Player, slot: any, trapId: any)
	-- lo slot e' una sola cifra ("1".."3"): niente "1.5", " 1", "01" che romperebbero le trappole
	if type(slot) ~= "string" or not string.match(slot, "^%d$") or type(trapId) ~= "string" then
		return
	end
	local def = Combat.Traps[trapId]
	local n = tonumber(slot)
	local plot = S.PlotService.Get(player)
	local data = S.DataService.Get(player)
	if not def or not n or n < 1 or n > Combat.TrapSlots or not plot or not data then
		return
	end
	if data.Traps[slot] then
		return -- gia' armata
	end
	if not S.DataService.SpendCoins(player, def.price, "Trap") then
		S.StateService.Notify(player, "NotEnoughCoins", nil, "Bad")
		return
	end
	S.StateService.Set(player, { "Traps", slot }, trapId)
	trapVisual(plot, slot, trapId)
	S.StateService.Effect(player, "Purchase", {})
end

local function triggerTrap(plot, owner: Player, slot: string, trapId: string, victim: Player)
	local def = Combat.Traps[trapId]
	S.StateService.Set(owner, { "Traps", slot }, nil)
	trapVisual(plot, slot, nil)
	if def.effect == "Slip" then
		local hrp = S.CharacterService.Root(victim)
		S.CarryService.DropAll(victim, "Trap")
		S.RagdollService.Ragdoll(victim, def.duration, (if hrp then hrp.CFrame.LookVector * 30 else Vector3.zero) + Vector3.new(0, 34, 0))
	elseif def.effect == "Slow" then
		S.CharacterService.ApplyEffect(victim, "Slow", def.duration)
	elseif def.effect == "Root" then
		S.CharacterService.ApplyEffect(victim, "Root", def.duration)
	end
	S.StateService.Notify(owner, "TrapTriggered", { name = victim.DisplayName }, "Good")
	S.StateService.Effect(nil, "Trap", { trap = trapId, position = plot.traps[tonumber(slot) :: number].Position })
end

---------------------------------------------------------------------------------------------

function DefenseService.Start()
	Net.Event("ToggleBarrier").OnServerEvent:Connect(DefenseService.ActivateBarrier)
	Net.Event("BuyTrap").OnServerEvent:Connect(buyTrap)
	for _, plot in S.PlotService.Plots do
		plot.consolePrompt.Triggered:Connect(function(who)
			if plot.owner == who then
				DefenseService.ActivateBarrier(who)
			end
		end)
	end
	S.PlotService.Assigned:Connect(function(player, plot)
		local data = S.DataService.Get(player)
		plot.consolePrompt.Enabled = true
		setBarrier(plot, false)
		player:SetAttribute("BarrierReadyAt", 0)
		for slot, trapId in table.clone(data.Traps) do
			-- toglie le chiavi non valide (salvate prima del controllo stretto sugli slot)
			if not string.match(slot, "^%d$") or not plot.traps[tonumber(slot) or 0] or not Combat.Traps[trapId] then
				data.Traps[slot] = nil
			else
				trapVisual(plot, slot, trapId)
			end
		end
	end)
	S.PlotService.Released:Connect(function(_player, plot)
		plot.consolePrompt.Enabled = false
		setBarrier(plot, false)
		for i = 1, Combat.TrapSlots do
			trapVisual(plot, tostring(i), nil)
		end
	end)
	-- allarme
	S.PlotService.Entered:Connect(function(player, plot)
		local owner = plot.owner
		if not owner or owner == player then
			return
		end
		local key = `{owner.UserId}:{player.UserId}`
		if os.clock() - (alarmSeen[key] or 0) > GameConfig.AlarmCooldown then
			alarmSeen[key] = os.clock()
			S.StateService.Notify(owner, "Intruder", { name = player.DisplayName }, "Bad")
			S.StateService.Effect(owner, "Alarm", {})
		end
	end)
	-- controllo delle trappole
	task.spawn(function()
		while true do
			task.wait(0.15)
			for _, plot in S.PlotService.Plots do
				local owner = plot.owner
				local data = owner and S.DataService.Get(owner)
				if data and next(data.Traps) then
					for slot, trapId in data.Traps do
						local spot = plot.traps[tonumber(slot) or 0]
						if not spot then
							continue -- dato non valido (salvataggi vecchi): ignorato
						end
						for _, other in Players:GetPlayers() do
							if other ~= owner then
								local hrp = S.CharacterService.Root(other)
								if hrp then
									local d = Vector3.new(hrp.Position.X - spot.Position.X, 0, hrp.Position.Z - spot.Position.Z).Magnitude
									if d < 2.8 and math.abs(hrp.Position.Y - spot.Position.Y) < 6 then
										triggerTrap(plot, owner, slot, trapId, other)
										break
									end
								end
							end
						end
					end
				end
			end
		end
	end)
end

return DefenseService
