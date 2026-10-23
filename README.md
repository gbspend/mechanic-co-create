# Mechanic Co-Create

A game built with [LÖVE](https://love2d.org/) 11.5.

## Running the game

1. Install [LÖVE 11.5](https://love2d.org/).
2. From the project folder, run:

   ```
   love .
   ```

   On Windows, if `love` isn't on your PATH:

   ```
   & "C:\Program Files\LOVE\lovec.exe" .
   ```

In VS Code, press `Ctrl+Shift+B` to run it.

## Controls

- **A/D or arrows**: move
- **Space / W / Up**: jump
- **F1**: show collision boxes
- **R**: reload the level
- **Esc**: quit

## Project layout

```
main.lua          Entry point: loads the level, handles input
conf.lua          Window and LÖVE settings
src/
  level.lua       Loads a map, sets up collisions, spawns entities, runs the camera
  player.lua      Player movement (Jump and Run) and tuning values
maps/
  level1.tmx      Level source, edit this in Tiled
  level1.lua      Lua export of level1.tmx, loaded by the game
  tilesets/       Tileset images
lib/
  sti/            Tiled map loader (Simple Tiled Implementation)
  bump.lua        Collision library
```

## Editing levels

Levels are made in [Tiled](https://www.mapeditor.org/).

1. Open `maps/level1.tmx` in Tiled and edit it.
2. Export with **File → Export As → Lua** to `maps/level1.lua` (overwrite it).
3. Press **R** in the game to reload.

Map rules:
- Tile layers with the custom property `collidable = true` are solid.
- The `Spawns` object layer needs an object named `player`.
- Tilesets must be embedded in the map, not separate `.tsx` files.
