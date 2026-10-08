--!strict
-- Elenco degli asset caricati su Roblox (generato da tools/upload_assets.py: non modificare a mano).
-- Models: modelli 3D (InsertService:LoadAsset) con le proprieta' di ogni parte.
-- Images / Sounds: id pronti per l'uso.

export type PartInfo = {
	name: string,
	color: { number },
	material: string,
	role: string,
	transparency: number?,
	reflectance: number?,
	group: string?,
	pivot: { number }?,
}

export type ModelInfo = {
	asset: number,
	kind: string,
	size: { number },
	parts: { PartInfo },
}

return {
	Models = {} :: { [string]: ModelInfo },
	Images = {} :: { [string]: string },
	Sounds = {} :: { [string]: string },
}
