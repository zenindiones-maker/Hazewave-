# FYAHREAPER touch layout for the test REAPER

- `make_icons.py` makes the 124 px touch icons (3-state strips) under `<resource>/Data/toolbar_icons{,/150,/200}`. Run it with Pillow. Then copy the same 124 px icons into the base folder: at ui_scale 2, REAPER uses the `200/` set.
- `reaper-menu.ini`: Toolbar 1 "Fyah Touch" (18 actions), plus the Main toolbar "Fyah Extras" (SAVE / MARKER / SEL ALL / TALL / UNSEL).
- `fyah_touch_layout.lua` runs from `Scripts/__startup.lua`. It hides the mixer and sets tracks to 150 px, so a track is about 9 mm on an A15 through the app.
- Toolbar 1 is docked at the top: `reaper.ini` has `dockermode15=2`, `dockheight_t=144`, and `[REAPERdockpref] toolbar=... 15`. I set this once in the UI (toolbar context menu: Position toolbar > In Docker, then Docker: Show in top of main window).
- Back up the configs before you apply this. The backups are in `fyahreaper-test/config-backup-*`.
