"""Generates data/parts_knowledge_graph.json (kept as a script so facilitators can edit the graph easily)."""
import json, pathlib
S = lambda i, n, c, r, note="": {"id": i, "type": "Supplier", "name": n, "country": c, "risk": r, "risk_note": note}
P = lambda i, n, cat, lt, stock, cost, sup: {"id": i, "type": "Part", "name": n, "category": cat, "lead_time_days": lt, "stock_weeks": stock, "unit_cost_eur": cost, "_sup": sup}
O = lambda i, n, attr, extra=None: {"id": i, "type": "Option", "name": n, "attribute": attr, **(extra or {})}

suppliers = [
    S("S-CHEMCO", "ChromaChem GmbH", "Germany", "low"),
    S("S-PIGASIA", "Pigmenta Asia Ltd", "India", "medium", "Single-source for red and fluorescent pigments; monsoon logistics delays"),
    S("S-ALUWORKS", "AluWorks Castings SA", "Spain", "medium", "Supplies all cast rims AND aluminium bonnet panels"),
    S("S-NORDAL", "NordAl Rolling AS", "Norway", "high", "Energy-price driven allocation; 84-day lead times"),
    S("S-SEMITW", "TaiSemi Corp", "Taiwan", "high", "Geopolitical and capacity risk; MCU allocation in force"),
    S("S-SEMIEU", "EuroSilicon AG", "Germany", "medium", "Qualified second source for MCU-9 family"),
    S("S-PLASTX", "PlastX Mouldings Ltd", "United Kingdom", "low"),
    S("S-TYRECO", "Grip & Co Tyres", "France", "low"),
    S("S-CARBON", "CarbonLab Srl", "Italy", "medium", "Small-volume carbon fibre; 8-week autoclave queue"),
    S("S-MIRRORTEK", "MirrorTek s.r.o.", "Czechia", "low"),
    S("S-SAFESYS", "SafeSys Restraints", "Sweden", "low"),
    S("S-STEELCO", "Ferro Steel SA", "Poland", "low"),
]
parts = [
    P("PR-01", "Epoxy primer", "paint", 14, 6, 3.1, "S-CHEMCO"),
    P("CC-02", "2K clearcoat", "paint", 21, 5, 4.4, "S-CHEMCO"),
    P("PG-RED-01", "Pyrrole red pigment", "pigment", 42, 3, 9.8, "S-PIGASIA"),
    P("PG-RED-02", "Quinacridone red pigment (alt)", "pigment", 28, 8, 11.2, "S-CHEMCO"),
    P("PG-BLU-02", "Phthalo blue pigment", "pigment", 21, 7, 7.5, "S-CHEMCO"),
    P("PG-TIO2", "Titanium dioxide white", "pigment", 30, 9, 2.2, "S-PIGASIA"),
    P("PEARL-MICA", "Pearl mica effect", "pigment", 45, 4, 6.0, "S-PIGASIA"),
    P("PG-CARB-BLK", "Carbon black pigment", "pigment", 14, 10, 1.4, "S-CHEMCO"),
    P("MF-AL-FLAKE", "Aluminium flake (metallic effect)", "pigment", 60, 3, 8.9, "S-NORDAL"),
    P("PG-FLUO-GRN", "Fluorescent green pigment", "pigment", 90, 0, 22.0, "S-PIGASIA"),
    P("PG-VIO-01", "Dioxazine violet pigment", "pigment", 49, 2, 14.5, "S-PIGASIA"),
    P("MIR-HOUSING", "Mirror housing & cap", "mirror", 21, 6, 18.0, "S-MIRRORTEK"),
    P("MIR-ACT", "Power-fold mirror actuator", "mirror", 35, 4, 26.0, "S-MIRRORTEK"),
    P("CF-PREPREG", "Carbon fibre prepreg", "material", 56, 2, 61.0, "S-CARBON"),
    P("CHIP-MCU-7", "MCU-7 automotive microcontroller", "electronics", 120, 2, 4.8, "S-SEMITW"),
    P("CHIP-MCU-9", "MCU-9 microcontroller (second source)", "electronics", 70, 5, 5.6, "S-SEMIEU"),
    P("BP-AL-02", "Aluminium bonnet panel", "body", 35, 4, 142.0, "S-ALUWORKS"),
    P("BP-ST-01", "Steel bonnet panel (flat)", "body", 21, 8, 64.0, "S-STEELCO"),
    P("BP-ST-02", "Steel bonnet panel (power dome)", "body", 21, 6, 71.0, "S-STEELCO"),
    P("RM-AL-6061", "Aluminium coil 6061", "raw_material", 84, 3, 3.9, "S-NORDAL"),
    P("RM-AL-6061-R", "Recycled aluminium coil 6061 (alt)", "raw_material", 45, 4, 4.3, "S-ALUWORKS"),
    P("RM-AL-A356", "Aluminium casting alloy A356", "raw_material", 84, 3, 3.2, "S-NORDAL"),
    P("SCOOP-INS", "Bonnet scoop insert", "body", 14, 10, 38.0, "S-PLASTX"),
    P("VENT-INS", "Bonnet vent louvre insert", "body", 14, 10, 22.0, "S-PLASTX"),
    P("STRIPE-VINYL", "Twin racing stripe vinyl", "trim", 7, 12, 45.0, "S-PLASTX"),
    P("AH-01", "Active pop-up bonnet actuator", "safety", 42, 3, 88.0, "S-SAFESYS"),
    P("RIM-5S-19", "19in 5-spoke cast rim", "wheel", 28, 5, 115.0, "S-ALUWORKS"),
    P("RIM-MS-20", "20in multi-spoke cast rim", "wheel", 35, 4, 148.0, "S-ALUWORKS"),
    P("RIM-AT-18", "18in all-terrain cast rim", "wheel", 28, 6, 104.0, "S-ALUWORKS"),
    P("RIM-TB-19", "19in turbine cast rim", "wheel", 28, 5, 121.0, "S-ALUWORKS"),
    P("AERO-COVER", "Turbine aero cover", "wheel", 14, 9, 19.0, "S-PLASTX"),
    P("RIM-ST-16", "16in steel rim", "wheel", 14, 12, 38.0, "S-STEELCO"),
    P("TY-235-40R19", "Tyre 235/40 R19", "tyre", 21, 7, 96.0, "S-TYRECO"),
    P("TY-245-35R20", "Tyre 245/35 R20", "tyre", 28, 5, 124.0, "S-TYRECO"),
    P("TY-AT-265-18", "All-terrain tyre 265/60 R18", "tyre", 35, 4, 131.0, "S-TYRECO"),
    P("TY-205-55R16", "Tyre 205/55 R16", "tyre", 14, 12, 58.0, "S-TYRECO"),
    P("TPMS-01", "Tyre pressure sensor", "electronics", 49, 3, 21.0, "S-MIRRORTEK"),
]
options = [
    O("RR-301", "Rosso Racing Red paint", "body_colour"), O("CR-305", "Crimson Velvet paint", "body_colour"),
    O("MB-118", "Midnight Sapphire paint", "body_colour"), O("GW-001", "Glacier White paint", "body_colour"),
    O("OB-900", "Obsidian Black paint", "body_colour"), O("LS-450", "Lunar Silver paint", "body_colour"),
    O("VL-777", "Volt Lime paint", "body_colour"), O("UV-610", "Ultraviolet paint", "body_colour"),
    O("MR-BODY", "Body-colour mirror caps", "mirror_colour"), O("MR-GB", "Gloss black mirror caps", "mirror_colour"),
    O("MR-SILVER", "Lunar Silver mirror caps", "mirror_colour"), O("MR-CARBON", "Carbon mirror caps", "mirror_colour", {"requires_trim": "GT"}),
    O("BN-FLAT", "Flat bonnet", "bonnet_design"), O("BN-DOME", "Power-dome bonnet", "bonnet_design"),
    O("BN-VENT", "Vented bonnet", "bonnet_design"), O("BN-SCOOP", "Bonnet scoop", "bonnet_design", {"requires_trim": "GT"}),
    O("BN-STRIPE", "Striped bonnet", "bonnet_design"),
    O("WH-5S-19", "19in Aero 5-spoke wheel set", "tyre_style"), O("WH-MS-20", "20in Multi-spoke wheel set", "tyre_style"),
    O("WH-AT-18", "18in All-terrain wheel set", "tyre_style", {"requires_body": "SUV"}), O("WH-TB-19", "19in Turbine wheel set", "tyre_style"),
    O("WH-ST-16", "16in Steel wheel set", "tyre_style"),
]
req = {
    "RR-301": ["PG-RED-01", "PR-01", "CC-02"], "CR-305": ["PG-RED-01", "MF-AL-FLAKE", "PR-01", "CC-02"],
    "MB-118": ["PG-BLU-02", "MF-AL-FLAKE", "PR-01", "CC-02"], "GW-001": ["PG-TIO2", "PEARL-MICA", "PR-01", "CC-02"],
    "OB-900": ["PG-CARB-BLK", "PR-01", "CC-02"], "LS-450": ["MF-AL-FLAKE", "PR-01", "CC-02"],
    "VL-777": ["PG-FLUO-GRN", "PR-01", "CC-02"], "UV-610": ["PG-VIO-01", "MF-AL-FLAKE", "PR-01", "CC-02"],
    "MR-BODY": ["MIR-HOUSING", "MIR-ACT"], "MR-GB": ["MIR-HOUSING", "MIR-ACT", "PG-CARB-BLK"],
    "MR-SILVER": ["MIR-HOUSING", "MIR-ACT", "MF-AL-FLAKE"], "MR-CARBON": ["MIR-HOUSING", "MIR-ACT", "CF-PREPREG"],
    "MIR-ACT": ["CHIP-MCU-7"],
    "BN-FLAT": ["BP-ST-01"], "BN-DOME": ["BP-ST-02"], "BN-VENT": ["BP-AL-02", "VENT-INS"],
    "BN-SCOOP": ["BP-AL-02", "SCOOP-INS", "AH-01"], "BN-STRIPE": ["BP-ST-01", "STRIPE-VINYL"],
    "BP-AL-02": ["RM-AL-6061"], "AH-01": ["CHIP-MCU-7"],
    "WH-5S-19": ["RIM-5S-19", "TY-235-40R19", "TPMS-01"], "WH-MS-20": ["RIM-MS-20", "TY-245-35R20", "TPMS-01"],
    "WH-AT-18": ["RIM-AT-18", "TY-AT-265-18", "TPMS-01"], "WH-TB-19": ["RIM-TB-19", "AERO-COVER", "TY-235-40R19", "TPMS-01"],
    "WH-ST-16": ["RIM-ST-16", "TY-205-55R16", "TPMS-01"],
    "RIM-5S-19": ["RM-AL-A356"], "RIM-MS-20": ["RM-AL-A356"], "RIM-AT-18": ["RM-AL-A356"], "RIM-TB-19": ["RM-AL-A356"],
    "TPMS-01": ["CHIP-MCU-7"],
}
alts = [("CHIP-MCU-7", "CHIP-MCU-9", "Requires 12-week software requalification"),
        ("PG-RED-01", "PG-RED-02", "Colour re-match to master panel required (T01)"),
        ("RM-AL-6061", "RM-AL-6061-R", "Approved; +0.4 EUR/kg")]
edges = []
for src, tgts in req.items():
    for t in tgts:
        edges.append({"source": src, "target": t, "type": "REQUIRES"})
for p in parts:
    edges.append({"source": p["id"], "target": p.pop("_sup"), "type": "SUPPLIED_BY"})
for a, b, note in alts:
    edges.append({"source": a, "target": b, "type": "ALTERNATIVE", "note": note})
kg = {"_about": "Meridian Motors parts knowledge graph (fictional). Nodes: Option (customer-facing spec choice), Part, Supplier. Edges: REQUIRES, SUPPLIED_BY, ALTERNATIVE. unit_cost_eur is CONFIDENTIAL and must never be disclosed by agents (see guardrails).",
      "confidential_fields": ["unit_cost_eur"],
      "nodes": options + parts + suppliers, "edges": edges}
out = pathlib.Path(__file__).resolve().parents[1] / "data" / "parts_knowledge_graph.json"
out.write_text(json.dumps(kg, indent=1))
print(f"wrote {out} with {len(kg['nodes'])} nodes and {len(edges)} edges")
