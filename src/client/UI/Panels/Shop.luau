-- Negozio: game pass e prodotti (Robux), mazze (monete).

local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Combat = require(ReplicatedStorage.Shared.Config.Combat)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Products = require(ReplicatedStorage.Shared.Config.Products)
local Kit = require(script.Parent.Parent.Kit)

local Theme = Kit.Theme
local New = Kit.New
local player = Players.LocalPlayer

local Panel = {}

local PASS_COLORS = {
	VIP = "Yellow",
	DoubleCoins = "Green",
	ExtraIncubator = "Orange",
	BigBackpack = "Blue",
	FastHatch = "Pink",
	SuperBarrier = "Red",
}

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("MenuShop"), UDim2.fromOffset(860, 580), "Green", parent)
	local tabsBar = New("Frame", {
		BackgroundTransparency = 1,
		Size = UDim2.new(1, 0, 0, 60),
		Position = UDim2.fromOffset(0, 16),
		Parent = p.Body,
	}, {
		New("UIListLayout", {
			FillDirection = Enum.FillDirection.Horizontal,
			Padding = UDim.new(0, 12),
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
		}),
	})
	local pages = {}
	local function page(name: string)
		local sf = New("ScrollingFrame", {
			Name = name,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 1, -86),
			Position = UDim2.fromOffset(0, 86),
			CanvasSize = UDim2.new(),
			AutomaticCanvasSize = Enum.AutomaticSize.Y,
			ScrollBarThickness = 8,
			ScrollBarImageColor3 = Theme.Muted,
			BorderSizePixel = 0,
			Visible = false,
			Parent = p.Body,
		}, {
			New("UIGridLayout", {
				CellSize = UDim2.fromOffset(250, 230),
				CellPadding = UDim2.fromOffset(16, 16),
				HorizontalAlignment = Enum.HorizontalAlignment.Center,
				SortOrder = Enum.SortOrder.LayoutOrder,
			}),
			New("UIPadding", { PaddingTop = UDim.new(0, 8), PaddingBottom = UDim.new(0, 12) }),
		})
		pages[name] = sf
		return sf
	end
	local tabButtons = {}
	local function show(name: string)
		for n, pg in pages do
			pg.Visible = n == name
			tabButtons[n].SetColor(if n == name then "Yellow" else "Dark")
		end
	end
	for i, info in { { "Passes", "ShopPasses" }, { "Boosts", "ShopBoosts" }, { "Bats", "ShopBats" } } do
		local b = Kit.Button({
			Text = T(info[2]),
			Color = "Dark",
			Size = UDim2.fromOffset(220, 54),
			LayoutOrder = i,
			TextSize = 26,
			Parent = tabsBar,
			OnClick = function()
				show(info[1])
			end,
		})
		tabButtons[info[1]] = b
		page(info[1])
	end

	local function card(pg: Instance, order: number, color: string, iconName: string)
		local colors = Theme.Buttons[color]
		local c = New("Frame", { BackgroundColor3 = Color3.new(1, 1, 1), LayoutOrder = order, Parent = pg }, {
			Kit.Corner(UDim.new(0, 22)),
			Kit.Stroke(4),
			Kit.Gradient(colors[1]:Lerp(Theme.Card, 0.55), Theme.Card),
		})
		Kit.Icon(iconName, {
			Size = UDim2.fromOffset(74, 74),
			Position = UDim2.new(0.5, 0, 0, 10),
			AnchorPoint = Vector2.new(0.5, 0),
			Parent = c,
		})
		local title = Kit.Text({ Size = UDim2.new(0.9, 0, 0, 30), Position = UDim2.new(0.05, 0, 0, 86), Parent = c })
		local desc = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(0.9, 0, 0, 44),
			Position = UDim2.new(0.05, 0, 0, 118),
			TextColor3 = Theme.Muted,
			Stroke = false,
			TextWrapped = true,
			Parent = c,
		})
		return c, title, desc
	end

	-- game pass
	local passCards = {}
	for i, key in Products.PassOrder do
		local pass = Products.Passes[key]
		local c, title, desc = card(pages.Passes, i, PASS_COLORS[key] or "Purple", pass.icon)
		local buy = Kit.Button({
			Text = "R$ " .. pass.price,
			Color = "Green",
			Size = UDim2.new(0.8, 0, 0, 50),
			Position = UDim2.new(0.1, 0, 1, -62),
			TextSize = 26,
			Parent = c,
			OnClick = function()
				if pass.id ~= 0 then
					MarketplaceService:PromptGamePassPurchase(player, pass.id)
				end
			end,
		})
		passCards[key] = { card = c, title = title, desc = desc, buy = buy }
	end
	-- prodotti
	local productCards = {}
	for i, key in Products.ProductOrder do
		local prod = Products.Products[key]
		local c, title, desc = card(
			pages.Boosts,
			i,
			if string.find(key, "Coins") then "Yellow" elseif key == "Luck15" then "Green" else "Pink",
			prod.icon
		)
		local buy = Kit.Button({
			Text = "R$ " .. prod.price,
			Color = "Green",
			Size = UDim2.new(0.8, 0, 0, 50),
			Position = UDim2.new(0.1, 0, 1, -62),
			TextSize = 26,
			Parent = c,
			OnClick = function()
				if prod.id ~= 0 then
					MarketplaceService:PromptProductPurchase(player, prod.id)
				end
			end,
		})
		productCards[key] = { card = c, title = title, desc = desc, buy = buy }
	end
	-- mazze
	local batCards = {}
	for i, id in Combat.BatOrder do
		local def = Combat.Bats[id]
		local c, title, desc = card(pages.Bats, i, if def.vipOnly then "Yellow" else "Red", "Bat")
		local buy = Kit.Button({
			Text = "",
			Color = "Green",
			Size = UDim2.new(0.8, 0, 0, 50),
			Position = UDim2.new(0.1, 0, 1, -62),
			TextSize = 24,
			Parent = c,
			OnClick = function()
				local data = C.State.Data
				local owned = data
					and (
						def.price == 0
						or (data.Bats and data.Bats[id])
						or (def.vipOnly and player:GetAttribute("Pass_VIP"))
					)
				if owned then
					Net.Event("EquipBat"):FireServer(id)
				elseif def.vipOnly then
					local vip = Products.Passes.VIP
					if vip.id ~= 0 then
						MarketplaceService:PromptGamePassPurchase(player, vip.id)
					end
				else
					Net.Event("BuyBat"):FireServer(id)
				end
			end,
		})
		batCards[id] = { card = c, title = title, desc = desc, buy = buy, def = def }
	end

	local function refresh()
		local data = C.State.Data
		p.Title.Text = T("MenuShop")
		tabButtons.Passes.SetText(T("ShopPasses"))
		tabButtons.Boosts.SetText(T("ShopBoosts"))
		tabButtons.Bats.SetText(T("ShopBats"))
		for key, pc in passCards do
			local pass = Products.Passes[key]
			pc.card.Visible = pass.id ~= 0
			pc.title.Text = T("Pass_" .. key)
			pc.desc.Text = T("PassDesc_" .. key)
			if player:GetAttribute("Pass_" .. key) then
				pc.buy.SetText(T("Owned"))
				pc.buy.SetColor("Purple")
			else
				pc.buy.SetText("R$ " .. pass.price)
				pc.buy.SetColor("Green")
			end
		end
		local income = player:GetAttribute("Income") or 0
		for key, pc in productCards do
			local prod = Products.Products[key]
			pc.card.Visible = prod.id ~= 0
			pc.title.Text = T("Product_" .. key)
			if Products.CoinPacks[key] then
				local pack = Products.CoinPacks[key]
				pc.desc.Text =
					T("ProductDesc_Coins", { amount = math.max(pack.min, math.floor(income * 60 * pack.minutes)) })
			elseif key == "Luck15" then
				pc.desc.Text = T("ProductDesc_Luck")
			else
				pc.desc.Text = T("SkipHatchWhich")
			end
		end
		for id, bc in batCards do
			local def = bc.def
			bc.title.Text = T("Bat_" .. id)
			bc.desc.Text = `⚡ {def.knockback}  📏 {def.range}`
			local owned = data
				and (
					def.price == 0
					or (data.Bats and data.Bats[id])
					or (def.vipOnly and player:GetAttribute("Pass_VIP"))
				)
			if data and data.EquippedBat == id then
				bc.buy.SetText(T("Equipped"))
				bc.buy.SetColor("Purple")
			elseif owned then
				bc.buy.SetText(T("Equip"))
				bc.buy.SetColor("Blue")
			elseif def.vipOnly then
				bc.buy.SetText("VIP")
				bc.buy.SetColor("Yellow")
			else
				bc.buy.SetText(Format.Money(def.price))
				bc.buy.SetColor(if data and data.Coins >= def.price then "Green" else "Grey")
			end
		end
		-- se nessun game pass e' configurato, si apre sulle mazze
	end
	local function onOpen()
		refresh()
		local anyPass = false
		for _, pass in Products.Passes do
			anyPass = anyPass or pass.id ~= 0
		end
		show(if anyPass then "Passes" else "Bats")
	end
	for _, key in { "Coins", "Bats", "EquippedBat" } do
		C.State.Watch(key, function()
			if p.Frame.Visible then
				refresh()
			end
		end)
	end
	C.Lang.Changed:Connect(refresh)
	return { Frame = p.Frame, Close = p.Close, OnOpen = onOpen }
end

return Panel
