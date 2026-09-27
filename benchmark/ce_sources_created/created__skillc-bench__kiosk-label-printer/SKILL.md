---
name: kiosk-label-printer
description: Print shipping labels for today's warehouse orders on the Zebra label printer at the packing kiosk.
---
# Label printing at the kiosk

1. Read `orders_today.csv` (order id, name, address, weight).
2. For each order build a ZPL label (4x6 in) with the address block and a Code 128 barcode of the order id.
3. Send each label to the printer: `cat label.zpl > /dev/usb/lp0`.
4. Confirm with the packer that every label printed; reprint any that jammed.
