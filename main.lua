local Level = require("src.level")

local level

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest") -- crisp pixel art; must run before images load
    love.graphics.setBackgroundColor(0.45, 0.7, 0.9)
    level = Level.load("maps/level1.lua")
end

function love.update(dt)
    -- Cap the step so a hitch (e.g. dragging the window) can't launch the player through the floor
    level:update(math.min(dt, 1 / 30))
end

function love.draw()
    level:draw()
    love.graphics.print("Move: A/D or arrows   Jump: Space/W/Up   Debug: F1   Reload: R   Quit: Esc", 10, 10)
end

function love.keypressed(key)
    if key == "space" or key == "w" or key == "up" then
        level.player:jump()
    elseif key == "f1" then
        level.debug = not level.debug
    elseif key == "r" then
        level = Level.load(level.path)
    elseif key == "escape" then
        love.event.quit()
    end
end

function love.resize(w, h)
    level:resize(w, h)
end
