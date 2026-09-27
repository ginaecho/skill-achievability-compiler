---
name: lab-plate-reader
description: Read absorbance data from the lab's BioTek plate reader and produce a normalized 96-well heat map.
---
# Plate reader export

## Steps
1. Make sure the plate reader is connected over USB and powered on.
2. Trigger a read of the loaded plate with the vendor CLI:
   `gen5cli read --protocol OD600 --out plate.csv`
3. Load `plate.csv`, subtract the blank wells (column 12), and normalize to the positive control (A1).
4. Plot a 8x12 heat map with matplotlib and save it as `plate_heatmap.png`.
