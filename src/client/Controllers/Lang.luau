-- Lingua del client (inglese o italiano) e traduzione dei testi, anche dei cartelli nel mondo.

local CollectionService = game:GetService("CollectionService")
local LocalizationService = game:GetService("LocalizationService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Signal = require(ReplicatedStorage.Shared.Util.Signal)
local Strings = require(ReplicatedStorage.Shared.Strings)

local Lang = {}

Lang.Current = "en"
Lang.Changed = Signal.new()

local C

function Lang.Init(controllers)
	C = controllers
	local ok, locale = pcall(function()
		return LocalizationService.RobloxLocaleId
	end)
	Lang.Current = Strings.LangFromLocale(if ok then locale else Players.LocalPlayer.LocaleId)
end

-- Traduce una chiave; gli argomenti che sono a loro volta chiavi (es. "Pet_Chick") vengono tradotti
function Lang.T(key: string, args: { [string]: any }?): string
	local resolved = nil
	if args then
		resolved = {}
		for k, v in args do
			if k == "rewardArgs" then
				continue
			end
			if type(v) == "string" and Strings.Has(v) then
				if k == "reward" and args.rewardArgs then
					resolved[k] = Lang.T(v, args.rewardArgs)
				else
					resolved[k] = Strings.Get(v, Lang.Current)
				end
			elseif type(v) == "number" and (k == "amount" or k == "price" or k == "coins") then
				resolved[k] = "$" .. require(ReplicatedStorage.Shared.Util.Format).Short(v)
			else
				resolved[k] = v
			end
		end
	end
	return Strings.Get(key, Lang.Current, resolved)
end

function Lang.Set(lang: string)
	if lang ~= "en" and lang ~= "it" then
		return
	end
	Lang.Current = lang
	Lang.Changed:Fire(lang)
	Lang.RefreshSigns()
end

local function refreshSign(label: Instance)
	if not label:IsA("TextLabel") then
		return
	end
	local key = label:GetAttribute("Key")
	if type(key) ~= "string" then
		return
	end
	local args = {}
	for name, value in label:GetAttributes() do
		if string.sub(name, 1, 4) == "Arg_" then
			args[string.sub(name, 5)] = value
		end
	end
	label.Text = Lang.T(key, args)
end

function Lang.RefreshSigns()
	for _, label in CollectionService:GetTagged("LocalizedSign") do
		refreshSign(label)
	end
end

function Lang.Start()
	CollectionService:GetInstanceAddedSignal("LocalizedSign"):Connect(refreshSign)
	Lang.RefreshSigns()
	-- preferenza salvata nelle impostazioni
	C.State.Watch("Settings", function(settings)
		if settings and (settings.Lang == "en" or settings.Lang == "it") and settings.Lang ~= Lang.Current then
			Lang.Set(settings.Lang)
		end
	end)
end

return Lang
