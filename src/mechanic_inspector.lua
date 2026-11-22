-- Mechanic inspector: the right-hand panel with the variable inspector and trigger/effect code boxes.
-- Every widget has its own height, so the content can grow past the window and scroll.
local utf8 = require("utf8")

local Inspector = {}
Inspector.__index = Inspector

local PAD         = 8
local GAP         = PAD -- space below a resizable widget; doubles as its drag handle
local HEADER_H    = 22
local LABEL_H     = 18
local MIN_BOX     = 24  -- smallest height a widget can be dragged to
local SCROLLBAR_W = 6
local WHEEL_STEP  = 40  -- pixels scrolled per mouse wheel notch

local colors = {
    panel   = { 0.12, 0.13, 0.16 },
    section = { 0.17, 0.18, 0.22 },
    box     = { 0.08, 0.09, 0.11 },
    border  = { 0.30, 0.32, 0.38 },
    focus   = { 0.45, 0.70, 0.90 },
    header  = { 1.00, 1.00, 1.00 },
    label   = { 0.65, 0.68, 0.75 },
    text    = { 0.90, 0.92, 0.95 },
}

local function clamp(v, lo, hi)
    return math.max(lo, math.min(v, hi))
end

-- Multi-line text box; the cursor always sits at the end of the text
local TextBox = {}
TextBox.__index = TextBox

function TextBox.new(label, h)
    return setmetatable({ label = label, text = "", x = 0, y = 0, w = 0, h = h }, TextBox)
end

function TextBox:contains(mx, my)
    return mx >= self.x and mx < self.x + self.w and my >= self.y and my < self.y + self.h
end

function TextBox:backspace()
    local offset = utf8.offset(self.text, -1)
    if offset then self.text = self.text:sub(1, offset - 1) end
end

function TextBox:draw(focused)
    local font = love.graphics.getFont()
    love.graphics.setColor(colors.label)
    love.graphics.print(self.label, self.x, self.y - LABEL_H + 2)

    love.graphics.setColor(colors.box)
    love.graphics.rectangle("fill", self.x, self.y, self.w, self.h)
    love.graphics.setColor(focused and colors.focus or colors.border)
    love.graphics.rectangle("line", self.x + 0.5, self.y + 0.5, self.w - 1, self.h - 1)

    -- Clip to the box and keep the end of the text (where the cursor is) in view
    local innerW = self.w - PAD * 2
    local shown = self.text
    if focused and love.timer.getTime() % 1 < 0.5 then shown = shown .. "_" end
    local _, lines = font:getWrap(shown, innerW)
    local textH = math.max(#lines, 1) * font:getHeight()
    local scroll = math.min(0, self.h - PAD * 2 - textH)

    local sx, sy, sw, sh = love.graphics.getScissor()
    love.graphics.intersectScissor(self.x + 1, self.y + 1, self.w - 2, self.h - 2)
    love.graphics.setColor(colors.text)
    love.graphics.printf(shown, self.x + PAD, self.y + PAD + scroll, innerW)
    love.graphics.setScissor(sx, sy, sw, sh)
end

function Inspector.new()
    local self = setmetatable({ boxes = {}, dividers = {}, scroll = 0, focused = nil, dragging = nil }, Inspector)
    self.sections = {
        { title = "Variable Inspector", body = { h = 120 } },
        { title = "Trigger" },
        { title = "On-Trigger Effect" },
        { title = "Per-Frame Effect" },
    }
    for _, s in ipairs(self.sections) do
        if not s.body then
            s.pseudo = TextBox.new("Pseudo code", 100)
            s.live   = TextBox.new("Live code", 100)
            table.insert(self.boxes, s.pseudo)
            table.insert(self.boxes, s.live)
        end
    end
    return self
end

-- Positions are in screen space with the scroll already applied, so hit tests and scissors just work
function Inspector:layout(x, y, w, h)
    self.x, self.y, self.w, self.h = x, y, w, h
    self.dividers = {}
    local function addDivider(target, left, width)
        table.insert(self.dividers, { target = target, x = left, y = target.y + target.h, w = width, h = GAP })
    end

    local cy = y + PAD - self.scroll
    for _, s in ipairs(self.sections) do
        s.x, s.y = x + PAD, cy
        s.w = w - PAD * 2 - SCROLLBAR_W
        if s.body then
            s.body.y = s.y + HEADER_H
            s.h = HEADER_H + s.body.h
            addDivider(s.body, s.x, s.w) -- handle sits in the gap below the section
        else
            -- Pseudo code on top, live code underneath
            local boxX, boxW = s.x + PAD, s.w - PAD * 2
            s.pseudo.x, s.pseudo.y, s.pseudo.w = boxX, s.y + HEADER_H + LABEL_H, boxW
            s.live.x, s.live.y, s.live.w = boxX, s.pseudo.y + s.pseudo.h + GAP + LABEL_H, boxW
            s.h = s.live.y + s.live.h + PAD - s.y
            addDivider(s.pseudo, boxX, boxW)
            addDivider(s.live, boxX, boxW)
        end
        cy = cy + s.h + PAD
    end

    self.contentH = cy + self.scroll - y
    local maxScroll = math.max(0, self.contentH - h)
    if self.scroll > maxScroll then
        self.scroll = maxScroll
        self:layout(x, y, w, h)
    end
end

function Inspector:relayout()
    self:layout(self.x, self.y, self.w, self.h)
end

function Inspector:contains(mx, my)
    return mx >= self.x and mx < self.x + self.w and my >= self.y and my < self.y + self.h
end

function Inspector:dividerAt(mx, my)
    if not self:contains(mx, my) then return end
    for _, d in ipairs(self.dividers) do
        if mx >= d.x and mx < d.x + d.w and my >= d.y and my < d.y + d.h then return d end
    end
end

function Inspector:draw()
    love.graphics.setColor(colors.panel)
    love.graphics.rectangle("fill", self.x, self.y, self.w, self.h)
    love.graphics.setScissor(self.x, self.y, self.w, self.h)

    for _, s in ipairs(self.sections) do
        love.graphics.setColor(colors.section)
        love.graphics.rectangle("fill", s.x, s.y, s.w, s.h, 4, 4)
        love.graphics.setColor(colors.header)
        love.graphics.print(s.title, s.x + PAD, s.y + 5)
        if s.pseudo then
            s.pseudo:draw(self.focused == s.pseudo)
            s.live:draw(self.focused == s.live)
        end
    end

    -- Grip line on the divider being hovered or dragged
    local d = self.dragging or self:dividerAt(love.mouse.getPosition())
    if d then
        love.graphics.setColor(colors.focus)
        love.graphics.rectangle("fill", d.x + d.w / 2 - 20, d.y + d.h / 2 - 1, 40, 2)
    end

    -- Scrollbar, only when the content is taller than the panel
    if self.contentH > self.h then
        local thumbH = math.max(20, self.h * self.h / self.contentH)
        local thumbY = self.y + (self.h - thumbH) * self.scroll / (self.contentH - self.h)
        love.graphics.setColor(colors.border)
        love.graphics.rectangle("fill", self.x + self.w - SCROLLBAR_W - 2, thumbY, SCROLLBAR_W, thumbH, 3, 3)
    end

    love.graphics.setScissor()
    love.graphics.setColor(1, 1, 1)
end

-- Input handlers return true when the inspector consumed the event

function Inspector:mousepressed(mx, my)
    self.dragging = self:dividerAt(mx, my)
    if self.dragging then return true end
    self.focused = nil
    if self:contains(mx, my) then
        for _, box in ipairs(self.boxes) do
            if box:contains(mx, my) then self.focused = box end
        end
    end
    love.keyboard.setKeyRepeat(self.focused ~= nil)
    return self.focused ~= nil
end

function Inspector:mousemoved(mx, my)
    local d = self.dragging
    if d then
        d.target.h = math.max(MIN_BOX, my - GAP / 2 - d.target.y)
        self:relayout()
    end
    local resizing = self.dragging or self:dividerAt(mx, my)
    love.mouse.setCursor(resizing and love.mouse.getSystemCursor("sizens") or nil)
end

function Inspector:mousereleased()
    self.dragging = nil
end

function Inspector:wheelmoved(dy)
    local mx, my = love.mouse.getPosition()
    if not self:contains(mx, my) then return false end
    self.scroll = clamp(self.scroll - dy * WHEEL_STEP, 0, math.max(0, self.contentH - self.h))
    self:relayout()
    -- Keep a drag going smoothly if the wheel is used mid-drag
    if self.dragging then self:mousemoved(mx, my) end
    return true
end

function Inspector:textinput(t)
    if not self.focused then return false end
    self.focused.text = self.focused.text .. t
    return true
end

function Inspector:keypressed(key)
    if not self.focused then return false end
    if key == "backspace" then
        self.focused:backspace()
    elseif key == "return" or key == "kpenter" then
        self.focused.text = self.focused.text .. "\n"
    elseif key == "tab" then
        self.focused.text = self.focused.text .. "    "
    elseif key == "escape" then
        self.focused = nil
        love.keyboard.setKeyRepeat(false)
    end
    return true
end

return Inspector
