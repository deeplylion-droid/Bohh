-- Avvio del client: inizializza i controller in ordine (Init senza attese, poi Start).

local Controllers = script.Parent:WaitForChild("Controllers")

local ORDER = {
	"State",
	"Lang",
	"Audio",
	"UI",
	"Notify",
	"Prompts",
	"World",
	"Carry",
	"Ragdoll",
	"Combat",
	"Obstacles",
	"Avalanche",
	"Guardians",
	"Zones",
	"Hatch",
	"Effects",
	"Tutorial",
	"ChatTags",
}

local C = {}
for _, name in ORDER do
	local module = Controllers:WaitForChild(name)
	C[name] = require(module)
end
for _, name in ORDER do
	if C[name].Init then
		C[name].Init(C)
	end
end
for _, name in ORDER do
	if C[name].Start then
		task.spawn(function()
			local ok, err = pcall(C[name].Start)
			if not ok then
				warn(`[Client] errore in {name}: {err}`)
			end
		end)
	end
end
