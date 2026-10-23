local player = { x = 640, y = 360, speed = 250, size = 24 }

function love.load()
    love.graphics.setBackgroundColor(0.1, 0.1, 0.12)
end

function love.update(dt)
    local dx, dy = 0, 0
    if love.keyboard.isDown("left", "a") then dx = dx - 1 end
    if love.keyboard.isDown("right", "d") then dx = dx + 1 end
    if love.keyboard.isDown("up", "w") then dy = dy - 1 end
    if love.keyboard.isDown("down", "s") then dy = dy + 1 end

    player.x = player.x + dx * player.speed * dt
    player.y = player.y + dy * player.speed * dt
end

function love.draw()
    love.graphics.setColor(0.9, 0.6, 0.2)
    love.graphics.rectangle("fill", player.x - player.size / 2, player.y - player.size / 2, player.size, player.size)

    love.graphics.setColor(1, 1, 1)
    love.graphics.print("WASD / arrows to move, Esc to quit", 10, 10)
end

function love.keypressed(key)
    if key == "escape" then
        love.event.quit()
    end
end
