local Level = require("src.level")
local Inspector = require("src.mechanic_inspector")

local level, inspector

-- The game takes the left half of the window, the mechanic inspector the right half
local function gameViewSize()
    local w, h = love.graphics.getDimensions()
    return math.floor(w / 2), h
end

local function layout(w, h)
    local gw = math.floor(w / 2)
    level:resize(gw, h)
    inspector:layout(gw, 0, w - gw, h)
end

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest") -- crisp pixel art; must run before images load
    love.graphics.setBackgroundColor(0.45, 0.7, 0.9)
    level = Level.load("maps/level1.lua", gameViewSize())
    inspector = Inspector.new()
    layout(love.graphics.getDimensions())
end

function love.update(dt)
    level.player.input_enabled = inspector.focused == nil
    -- Cap the step so a hitch (e.g. dragging the window) can't launch the player through the floor
    level:update(math.min(dt, 1 / 30))
end

function love.draw()
    local gw, gh = gameViewSize()
    love.graphics.setScissor(0, 0, gw, gh) -- keep debug boxes out of the inspector
    level:draw()
    love.graphics.print("Move: A/D or arrows   Jump: Space/W/Up   Debug: F1   Reload: R   Quit: Esc", 10, 10)
    love.graphics.setScissor()
    inspector:draw()
end

function love.keypressed(key)
    if inspector:keypressed(key) then return end
    if key == "space" or key == "w" or key == "up" then
        level.player:jump()
    elseif key == "f1" then
        level.debug = not level.debug
    elseif key == "r" then
        level = Level.load(level.path, gameViewSize())
    elseif key == "escape" then
        love.event.quit()
    end
end

function love.textinput(t)
    inspector:textinput(t)
end

function love.mousepressed(x, y)
    inspector:mousepressed(x, y)
end

function love.mousemoved(x, y)
    inspector:mousemoved(x, y)
end

function love.mousereleased()
    inspector:mousereleased()
end

function love.wheelmoved(_, dy)
    inspector:wheelmoved(dy)
end

function love.resize(w, h)
    layout(w, h)
end
