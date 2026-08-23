# Deterministic seed catalog

`catalog.json` contains fixed IDs for 20 products, 28 ingredients, and a BOM for every product. Eight ingredients explicitly carry `vision_recognized: true` for edge integration fixtures. Tracked ingredients use a documented inventory snapshot at `store-main/bar`; unlimited ingredients deliberately have no inventory row.

Run `make seed` after `make migrate`. The loader upserts identities and replaces the demo stock snapshot, so repeated runs neither duplicate rows nor add quantity.
