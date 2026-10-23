-- Loads a Tiled map (Lua export), builds its bump world, spawns entities and runs the camera.
local sti    = require("lib.sti")
local bump   = require("lib.bump")
local Player = require("src.player")

local Level = {}
Level.__index = Level

function Level.load(path)
    local self = setmetatable({ path = path, debug = false }, Level)

    self.map   = sti(path, { "bump" })
    self.world = bump.newWorld(self.map.tilewidth)
    self.map:bump_init(self.world) -- adds every tile from layers marked collidable

    self.width  = self.map.width * self.map.tilewidth
    self.height = self.map.height * self.map.tileheight

    -- Entities come from the "Spawns" object layer
    for _, obj in ipairs(self.map.layers["Spawns"].objects) do
        if obj.name == "player" then
            self.spawn  = { x = obj.x, y = obj.y }
            self.player = Player.new(self.world, obj.x, obj.y)
        end
    end
    assert(self.player, path .. " has no object named 'player' in its Spawns layer")
    self.map:removeLayer("Spawns")

    -- Draw entities as part of the map so they share its camera offset
    local entities = self.map:addCustomLayer("Entities")
    entities.draw = function() self.player:draw() end

    self.camX, self.camY = 0, 0
    return self
end

function Level:update(dt)
    self.map:update(dt)
    self.player:update(dt)

    -- Fell out of the level
    if self.player.y > self.height then
        self.player:teleport(self.spawn.x, self.spawn.y)
    end

    self:updateCamera()
end

function Level:updateCamera()
    local sw, sh = love.graphics.getDimensions()
    local p = self.player
    local x = p.x + p.w / 2 - sw / 2
    local y = p.y + p.h / 2 - sh / 2
    -- Keep the camera inside the map
    self.camX = math.floor(math.max(0, math.min(x, self.width - sw)))
    self.camY = math.floor(math.max(0, math.min(y, self.height - sh)))
end

function Level:draw()
    self.map:draw(-self.camX, -self.camY)
    if self.debug then
        love.graphics.setColor(1, 0, 0)
        self.map:bump_draw(-self.camX, -self.camY)
        love.graphics.setColor(1, 1, 1)
    end
end

function Level:resize(w, h)
    self.map:resize(w, h)
end

return Level
