# Third-party assets

Every file under this directory is CC0 1.0 (public domain dedication) and stored exactly as published. `tools/thirdparty/fetch_cc0.sh` re-downloads all of them. Attribution is not required by CC0; it is recorded here so sources stay traceable (PLAN.md 13.8).

| Path | Asset | Source | Licence | Used in |
|---|---|---|---|---|
| `ambientcg/Carpet012/` | Carpet 012, 2K JPG (colour, normal GL, roughness, AO) | https://ambientcg.com/view?id=Carpet012 | CC0 | `materials/mat_office_carpet.tres` (Night Shift office floor) |
| `ambientcg/OfficeCeiling001/` | Office Ceiling 001, 2K JPG | https://ambientcg.com/view?id=OfficeCeiling001 | CC0 | `materials/mat_ceiling_tiles.tres` (Night Shift office ceiling) |
| `polyhaven/painted_plaster_wall/` | Painted Plaster Wall, 2k JPG (diff, nor_gl, arm) | https://polyhaven.com/a/painted_plaster_wall | CC0 | `materials/mat_painted_plaster.tres` (Night Shift walls) |
| `polyhaven/desk_lamp_arm_01/` | Desk Lamp Arm 01, 1k glTF | https://polyhaven.com/a/desk_lamp_arm_01 | CC0 | Night Shift desk lamp |
| `polyhaven/mounted_fluorescent_lights/` | Mounted Fluorescent Lights, 1k glTF (variant `d` used) | https://polyhaven.com/a/mounted_fluorescent_lights | CC0 | Night Shift ceiling battens |
| `polyhaven/office_notepads/` | Office Notepads, 1k glTF (`a4_stack`, `sticky_stack` used) | https://polyhaven.com/a/office_notepads | CC0 | Night Shift desk décor |
| `polyhaven/clipboard/` | Clipboard, 1k glTF | https://polyhaven.com/a/clipboard | CC0 | Night Shift filing cabinet décor |
| `polyhaven/cardboard_box_01/` | Cardboard Box 01, 1k glTF | https://polyhaven.com/a/cardboard_box_01 | CC0 | Night Shift migration boxes |
| `polyhaven/fire_alarm/` | Fire Alarm (manual call point), 1k glTF | https://polyhaven.com/a/fire_alarm | CC0 | Night Shift, beside the exit door |
| `polyhaven/security_camera_02/` | Security Camera 02, 1k glTF | https://polyhaven.com/a/security_camera_02 | CC0 | Night Shift office ceiling corner |
| `polyhaven/stationery_supplies/` | Stationery Supplies, 1k glTF | https://polyhaven.com/a/stationery_supplies | CC0 | not placed yet (M4 desk dressing) |

Known budget exception: `desk_lamp_arm_01` is about 25.7k polygons, over the 20k prop budget (PLAN.md 13.8). Accepted for the M1 look test; a Codex decimation pass is listed for M4.
