# Quick human review — PROVISIONAL / AUTO-LABELED

All five questions remain `verified=false`. These source-PDF excerpts are review prompts, not certified answers. Check the rendered page and the proposed chunk IDs in `chunks.json` before accepting a label.

## q010 — exact_technical_value

**Question:** What is the rated power input of the Bosch GKS 65 GCE Professional?

**Source:** `data/manuals/gks_65_gce_professional.pdf`, PDF p8. Proposed chunk IDs: `gks_65_gce_professional.pdf:p8:c4`.

**Source-PDF text excerpt:**

```text
Circular Saw
GKS 65
Professional
GKS 65 G
Professional
GKS 65 GCE
Professional
Article number
3 601 F67 0..
3 601 F68 9..
3 601 F68 9..
Rated power input
W
1600
1600
1800
No-load speed
min-1
5900
5900
2300 – 5000
Rotational speed under load, max.
min-1
4200
4200
1400 – 4000
Cutting depth, max.
– for 0° bevel angle
– for 45° bevel angle
mm
mm
65
48
65
48
65
48
Spindle lock
z
z
z
Speed preselection
–
–
z
Constant electronic control
–
–
z
Temperature Dependent Overload Protection
–
–
z
Reduced starting current
–
–
z
Base plate dimensions
```

**Review focus:** confirm the stated model, condition, value/wording, page, and chunk relevance.

## q018 — equipment_model_distinction

**Question:** Which ACRC301 package lists two pipe gaskets for unit pipes rather than four undifferentiated pipe gaskets: ACRC301S or ACRC301H?

**Source:** `data/manuals/990_4705_InRow_Chilled_Water_Air_Conditioners_300_Installation_Manual.pdf`, PDF p15. Proposed chunk IDs: `990_4705_InRow_Chilled_Water_Air_Conditioners_300_Installation_Manual.pdf:p15:c1|990_4705_InRow_Chilled_Water_Air_Conditioners_300_Installation_Manual.pdf:p16:c1`.

**Source-PDF text excerpt:**

```text
Package Contents—ACRC301S
na4465a
Item
Description
Quantity
Item
Quantity
InRow RC—ACRC301S
1
Insulation, bracket
2
Front and rear panel key
2
TORX screw
4
Remote temperature
probe
1
Phillips screw, black
4
Remote temperature
probe clip
3
Wire tie
3
Pipe gasket
4
Barb-type wire tie
3
Pipe, outlet
1
Bolt down kit
1
Pipe, inlet
1
Power cord, IEC 309-
16A to C19
2
Insulation, outlet pipe
(above clamp)
1
Power cord, NEMA L5-
20P to C19
2
Insulation, inlet pipe
(above clamp)
1
Terminator
1
Insulation, union
2
Terminal p
```

**Also inspect PDF p16:**

```text
Package Contents—ACRC301H
na4398a
Item
Description
Quantity
Item
Quantity
InRow RC—ACRC301H
1
Insulation, clamp
2
Front and rear panel key
2
TORX screw
4
Remote temperature
probe
1
Phillips screw, black
4
Remote temperature
probe clip
3
Wire tie
3
Pipe gasket, unit pipes
2
Barb-type wire tie
3
Pipe, inlet
1
Bolt down kit
1
Pipe, outlet
1
Pipe gasket, client
connections
2
Insulation, outlet pipe
(above clamp)
1
Terminator
1
Insulation, inlet pipe
(above clamp)
1
Terminal plug, 3-
position
2
Insul
```

**Review focus:** confirm the stated model, condition, value/wording, page, and chunk relevance.

## q020 — paraphrased

**Question:** Which GPS pump variant is suited to high head pressure with low flow rate?

**Source:** `data/manuals/STULZ_Glycol_Systems_Engineering_Manual.pdf`, PDF p5. Proposed chunk IDs: `STULZ_Glycol_Systems_Engineering_Manual.pdf:p5:c1`.

**Source-PDF text excerpt:**

```text
Pressure Drop/Flow Rate Curves 
This section provides pressure drop/ﬂow rate curves for the different GPS pump models. The GPS series provides 
one to three models per HP rating, speciﬁed as A, B, or C in the model number. The A models are ideal for 
applications with high head pressures with low ﬂow rate. The B models are best for average head pressure and 
ﬂow rate to achieve higher efﬁciencies. The C models are designed for situations of low head pressures and high 
ﬂow rates. 
A graph containing a pressure drop curve is provided for each model. Note that curves reflect 40% Ethylene Glycol at 45 °.
```

**Review focus:** confirm the stated model, condition, value/wording, page, and chunk relevance.

## q027 — table_based

**Question:** For CyberOne DX model 042 in cooling-only mode at 208/3/60 how does adding a condensate pump change the MCA?

**Source:** `data/manuals/STULZ CyberOne DX Engineering Manual.pdf`, PDF p24. Proposed chunk IDs: `STULZ CyberOne DX Engineering Manual.pdf:p24:c1|STULZ CyberOne DX Engineering Manual.pdf:p24:c2|STULZ CyberOne DX Engineering Manual.pdf:p24:c3`.

**Source-PDF text excerpt:**

```text
Cooling Only
208/3/60
No
N/A
N/A
27.8
40
30.1
45
47.3
70
57.8
90
208/3/60
Yes
N/A
N/A
29.9
45
32.2
45
49.4
70
59.9
90
460/3/60
No
N/A
N/A
13.7
20
15.1
20
23.1
35
26.2
40
460/3/60
Yes
N/A
N/A
14.5
20
15.9
20
23.9
35
27.0
40
575/3/60
No
N/A
N/A
10.4
15
12.8
15
17.3
25
19.3
30
575/3/60
Yes
N/A
N/A
11.0
15
13.4
20
17.9
25
19.9
30
NOTE: Electrical data is based o
```

**Review focus:** the model/MCA header is separated from the cooling-only rows in saved chunks; confirm the 042 column and pump No/Yes association.

## q029 — unanswerable

**Question:** What is the official list price in US dollars for a CyberRow DX CRS-042?

**Source:** `data/manuals/STULZ CyberRow DX Engineering Manual QEWR002L.pdf`, PDF p13. Proposed chunk IDs: `none`.

**Source-PDF text excerpt:**

```text
Model: CRS-
042
084
Voltages
MCA
MFS
MCA
MFS
Cooling Only (Includes Condensate Pump)
208 V / 1 PH / 60 Hz
31.9
50
39.3
60
208 V / 3 PH / 60 Hz
25.6
40
38.1
60
460 V / 3 PH / 60 Hz
12.2
15
18.8
30
575 V / 3 PH / 60 Hz
10
15
13.7
20
Electrical Data
Models 042 - 084
```

**Absence check:** automatic scan of all 50 indexed PDFs found no `price` or `msrp` text. Confirm visually and consider other wording before accepting an unanswerable label.

