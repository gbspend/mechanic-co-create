-- Player with the Jump and Run mechanics, colliding with the level through bump.
-- Screen space: y points down, so "up" is negative y.
local Player = {}
Player.__index = Player

Player.speed        = 220   -- Run: horizontal speed (px/s)
Player.jump_power   = 620   -- Jump: initial upward speed (px/s)
Player.jump_gravity = 1500  -- Jump: gravity while rising (lower = floatier)
Player.fall_gravity = 2600  -- Jump: gravity while falling (higher = heavier)
Player.air_control  = false -- Run: read input while airborne

local function getAxis()
    local x = 0
    if love.keyboard.isDown("left", "a") then x = x - 1 end
    if love.keyboard.isDown("right", "d") then x = x + 1 end
    return x
end

function Player.new(world, x, y, w, h)
    local self = setmetatable({
        world = world,
        x = x, y = y,
        w = w or 24, h = h or 28,
        vx = 0, vy = 0,
        ax = 0, ay = 0,
        input_x = 0,
        on_ground = false,
    }, Player)
    world:add(self, self.x, self.y, self.w, self.h)
    return self
end

function Player:jump()
    if self.on_ground then
        self.vy = -self.jump_power
        self.on_ground = false
    end
end

function Player:teleport(x, y)
    self.x, self.y = x, y
    self.vx, self.vy = 0, 0
    self.world:update(self, x, y)
end

function Player:update(dt)
    -- Run
    if self.on_ground or self.air_control then
        self.input_x = getAxis()
    end
    self.vx = self.input_x * self.speed

    -- Jump: Verlet step with separate rising/falling gravity
    if self.vy < 0 then
        self.ay = self.jump_gravity
    else
        self.ay = self.fall_gravity
    end

    local goalX = self.x + self.vx * dt
    local goalY = self.y + self.vy * dt + 0.5 * self.ay * dt * dt
    self.vy = self.vy + self.ay * dt

    -- Collide. bump moves us as far as it can toward the goal and reports what we hit.
    local cols, len
    self.x, self.y, cols, len = self.world:move(self, goalX, goalY)

    self.on_ground = false
    for i = 1, len do
        local normal = cols[i].normal
        if normal.y < 0 then
            -- landed on top of something
            self.on_ground = true
            self.vy = 0
        elseif normal.y > 0 and self.vy < 0 then
            -- bumped our head
            self.vy = 0
        end
    end
end

function Player:draw()
    love.graphics.setColor(0.95, 0.6, 0.2)
    love.graphics.rectangle("fill", self.x, self.y, self.w, self.h)
    love.graphics.setColor(1, 1, 1)
end

return Player
