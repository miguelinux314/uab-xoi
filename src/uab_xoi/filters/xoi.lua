-- Pandoc Lua filter turning the book's LaTeX constructs into mkdocs-material
-- markdown. Configuration comes from environment variables set by tex2md.py.

local cfg = {
  lang = os.getenv("XOI_LANG") or "en",
  page = os.getenv("XOI_PAGE") or "index.md",
  chapnum = os.getenv("XOI_CHAPNUM") or "",
  root = os.getenv("XOI_ROOT") or ".",
  labels_path = os.getenv("XOI_LABELS"),
  concepts_path = os.getenv("XOI_CONCEPTS"),
  assets = os.getenv("XOI_ASSETS") or "assets/",
}

local T = {
  en = {remark = "Note", exercise = "Exercise", output = "Output", code = "Code"},
  es = {remark = "Nota", exercise = "Ejercicio", output = "Salida", code = "Código"},
  ca = {remark = "Nota", exercise = "Exercici", output = "Sortida", code = "Codi"},
}
local t = T[cfg.lang] or T.en

local WRITER = "gfm+attributes+tex_math_dollars"

local labels = {}
if cfg.labels_path then
  local f = io.open(cfg.labels_path, "r")
  if f then
    labels = pandoc.json.decode(f:read("a"))
    f:close()
  end
end

local concept_n = 0
local exercise_n = 0
local section = {num = "", title = ""}
local concepts_out = cfg.concepts_path and io.open(cfg.concepts_path, "a")

local function slug(label)
  return (label:gsub("[^%w%-_]", "-"))
end

local function dirname(path)
  return path:match("^(.*)/[^/]*$") or ""
end

-- Relative link from the current page to another page file (mkdocs resolves
-- links between .md files).
local function relpath(target)
  local here = dirname(cfg.page)
  if here == "" then return target end
  local up = ""
  for _ in here:gmatch("[^/]+") do up = up .. "../" end
  return up .. target
end

local function write_md(blocks)
  return pandoc.write(pandoc.Pandoc(blocks), WRITER, {wrap_text = "none"})
end

local function indent(text)
  return (text:gsub("([^\n]+)", "    %1"))
end

local function admonition(kind, title, blocks, anchor)
  local head = anchor and ('<a id="' .. anchor .. '"></a>\n') or ""
  return pandoc.RawBlock("markdown",
    head .. '!!! ' .. kind .. ' "' .. title .. '"\n' .. indent(write_md(blocks)) .. "\n")
end

local function read_file(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local s = f:read("a")
  f:close()
  -- Program output may contain raw bytes; show them as \xNN like a REPL would.
  return (s:gsub("[%z\1-\8\11\12\14-\31\127]", function(c)
    return string.format("\\x%02x", c:byte())
  end))
end

local function is_blank_inline(il)
  return il.t == "Space" or il.t == "SoftBreak" or il.t == "LineBreak"
    or (il.t == "Str" and il.text:match("^[%s\194\160]*$"))
end

local function first_label_span(blocks)
  local found
  pandoc.Pandoc(blocks):walk({Span = function(s)
    if not found and s.identifier ~= "" then found = s.identifier end
  end})
  return found
end

------------------------------------------------------------------------------
-- Pass 1 (top-down): header levels, section tracking, marker links, numbering
------------------------------------------------------------------------------

local function pass1(doc)
  local min_level = 6
  for _, b in ipairs(doc.blocks) do
    if b.t == "Header" and b.level < min_level then min_level = b.level end
  end
  local shift = tonumber(os.getenv("XOI_HEADER_SHIFT")) or (1 - min_level)

  local filter = {traverse = "topdown"}

  function filter.Header(el)
    el.level = el.level + shift
    local info = labels[el.identifier]
    if el.identifier:find(":") then el.identifier = slug(el.identifier) end
    el.classes = {}
    -- Unnumbered (sub)sections inherit the number of the enclosing numbered one.
    local num = (info and info.num ~= "" and info.num) or section.num
    section = {num = num, title = pandoc.utils.stringify(el.content)}
    -- A heading with its own PDF section number (info.num - unnumbered
    -- \section*{} etc. have none) shows that number, same as the PDF; this
    -- is what the left nav label (page title, from the H1) and the
    -- right-hand "Table of contents" panel (built from heading text) end up
    -- showing too, since both just read the rendered heading text.
    if info and info.num ~= "" then
      local prefixed = pandoc.List({pandoc.Str(info.num), pandoc.Space()})
      prefixed:extend(el.content)
      el.content = prefixed
    end
    return el
  end

  function filter.Div(el)
    if el.classes[1] == "exercise" then
      exercise_n = exercise_n + 1
      el.attributes["num"] = (cfg.chapnum ~= "" and (cfg.chapnum .. ".") or "") .. exercise_n
    end
    return el
  end

  function filter.Link(el)
    local target = el.target
    local key = target:match("^#concept:(.*)$")
    if key then
      concept_n = concept_n + 1
      local id = "c" .. concept_n
      if concepts_out then
        concepts_out:write(pandoc.json.encode({
          key = key, text = pandoc.utils.stringify(el.content), page = cfg.page,
          anchor = id, secnum = section.num, sectitle = section.title}) .. "\n")
      end
      -- Concepts can nest (\conceptRef{..}{... \concept{x} ...}).
      local inner = pandoc.Span(el.content):walk({Link = filter.Link}).content
      local out = pandoc.List({pandoc.RawInline("html", '<span class="concept" id="' .. id .. '">')})
      out:extend(inner)
      out:insert(pandoc.RawInline("html", "</span>"))
      return out
    end
    local node = target:match("^#node:(.*)$")
    if node then
      local out = pandoc.List({pandoc.RawInline("html", '<span class="node">')})
      out:extend(el.content)
      out:insert(pandoc.RawInline("html", "</span>"))
      return out
    end
    if target:match("^#codefile:") then return el end
    local label = target:match("^#(.*)$")
    if label then
      local info = labels[label]
      local is_ref = el.attributes["reference-type"] ~= nil
      if not info then
        if is_ref then
          io.stderr:write("xoi.lua: unresolved reference " .. label .. " in " .. cfg.page .. "\n")
          return pandoc.Str("[?]")
        end
        return el
      end
      local href = relpath(info.page) .. "#" .. slug(label)
      local content = el.content
      if is_ref then content = {pandoc.Str(info.num ~= "" and info.num or info.title)} end
      return pandoc.Link(content, href)
    end
    return el
  end

  return doc:walk(filter)
end

------------------------------------------------------------------------------
-- Pass 2 (bottom-up): environments -> admonitions, code blocks, cleanup
------------------------------------------------------------------------------

-- Appends `text` to `parts`, one entry per line, each indented 4 spaces (the
-- nesting pymdownx.tabbed requires for a tab's content) - blank lines are
-- left empty rather than turned into trailing whitespace.
local function add_indented_lines(parts, text)
  for line in (text .. "\n"):gmatch("(.-)\n") do
    parts[#parts + 1] = (line == "") and "" or ("    " .. line)
  end
end

local function showcode(el, with_output)
  local path
  pandoc.Pandoc(el.content):walk({Link = function(l)
    path = path or l.target:match("^#codefile:(.*)$")
  end})
  if not path then return el end
  local code = (read_file(cfg.root .. "/code/" .. path) or ("<missing: code/" .. path .. ">")):gsub("%s+$", "")
  local py_url = cfg.assets .. "code/" .. path
  -- Raw <a download> (not a markdown link): forces a download instead of
  -- navigating to the raw file, which is the browser's default for .py/.out.
  local links = '<a href="' .. py_url .. '" download>.py</a>'
  local parts = { '<div class="showcode" markdown="1">' }

  if with_output then
    local out = (read_file(cfg.root .. "/code/" .. path .. ".out") or ""):gsub("%s+$", "")
    links = links .. ' &middot; <a href="' .. py_url .. '.out" download>.out</a>'
    parts[#parts + 1] = "**`" .. path .. "`** (" .. links .. ")"
    parts[#parts + 1] = ""
    -- pymdownx.tabbed (=== "Title"): a Code/Output tab pair instead of two
    -- stacked fenced blocks.
    parts[#parts + 1] = '=== "' .. t.code .. '"'
    parts[#parts + 1] = '    ```python linenums="1"'
    add_indented_lines(parts, code)
    parts[#parts + 1] = "    ```"
    parts[#parts + 1] = ""
    parts[#parts + 1] = '=== "' .. t.output .. '"'
    parts[#parts + 1] = '    ```text'
    add_indented_lines(parts, out)
    parts[#parts + 1] = "    ```"
  else
    parts[#parts + 1] = "**`" .. path .. "`** (" .. links .. ")"
    parts[#parts + 1] = ""
    parts[#parts + 1] = '```python linenums="1"'
    parts[#parts + 1] = code
    parts[#parts + 1] = "```"
  end
  parts[#parts + 1] = "</div>"
  return pandoc.RawBlock("markdown", table.concat(parts, "\n") .. "\n")
end

local pass2 = {}

function pass2.Div(el)
  local cls = el.classes[1]
  if cls == "remark" then
    return admonition("note", t.remark, el.content)
  elseif cls == "exercise" then
    local num = el.attributes["num"] or ""
    local label = first_label_span(el.content)
    return admonition("example", t.exercise .. (num ~= "" and (" " .. num) or ""),
                      el.content, label and slug(label))
  elseif cls == "showcode" then
    return showcode(el, true)
  elseif cls == "showcodenooutput" then
    return showcode(el, false)
  elseif cls == "wrapfigure" then
    return pandoc.Div(el.content):walk({Image = function(img)
      img.classes = {"wrap"}
      return img
    end}).content
  elseif cls == "figurerow" then
    -- 2+ \includegraphics in a row in the source (src/uab_xoi/tex2md.py) - lay
    -- them out side by side like the PDF instead of stacking each full-width
    -- (web/css/xoi.css .figure-row).
    return pandoc.RawBlock("markdown",
      '<div class="figure-row" markdown="1">\n\n' .. write_md(el.content) .. '\n\n</div>')
  elseif cls == "captionedfigure" then
    -- \captionedimage (src/uab_xoi/tex2md.py): linked image with a centered caption
    -- below; consecutive ones sit side by side (web/css/xoi.css .captioned-figure).
    return pandoc.RawBlock("markdown",
      '<div class="captioned-figure" markdown="1">\n\n' .. write_md(el.content) .. '\n\n</div>')
  elseif cls == "center" or cls == "flushleft" or cls == "flushright" or cls == "minipage" then
    -- A \begin{center} holding \captionedimage figures keeps them centered as a row.
    if cls == "center" then
      for _, b in ipairs(el.content) do
        if b.t == "RawBlock" and b.text:find("captioned%-figure") then
          local out = pandoc.List({pandoc.RawBlock("markdown", '<div class="captioned-row" markdown="1">\n')})
          out:extend(el.content)
          out:insert(pandoc.RawBlock("markdown", "\n</div>"))
          return out
        end
      end
    end
    return el.content
  end
  return el
end

function pass2.Para(el)
  local content = pandoc.List()
  local started = false
  for _, il in ipairs(el.content) do
    if started or not is_blank_inline(il) then
      started = true
      content:insert(il)
    end
  end
  while #content > 0 and is_blank_inline(content[#content]) do content:remove() end
  if #content == 0 then return {} end
  el.content = content
  return el
end

function pass2.Plain(el)
  return pass2.Para(el)
end

function pass2.DefinitionList(el)
  local items = pandoc.List()
  for _, item in ipairs(el.content) do
    local term, defs = item[1], item[2]
    local blocks = pandoc.List()
    local first = pandoc.List({pandoc.Strong(term), pandoc.Space()})
    local body = defs[1] or {}
    if body[1] and (body[1].t == "Para" or body[1].t == "Plain") then
      first:extend(body[1].content)
      blocks:insert(pandoc.Para(first))
      for i = 2, #body do blocks:insert(body[i]) end
    else
      blocks:insert(pandoc.Para(first))
      blocks:extend(body)
    end
    items:insert(blocks)
  end
  return pandoc.BulletList(items)
end

local function filled_cells(row)
  local n = 0
  for _, cell in ipairs(row.cells) do
    if pandoc.utils.stringify(cell.contents) ~= "" then n = n + 1 end
  end
  return n
end

-- LaTeX tables have no header semantics: use the first meaningful row as the
-- header, dropping decorative rows above it (e.g. a single spanning title).
function pass2.Table(el)
  local head = pandoc.List()
  for _, row in ipairs(el.head.rows) do
    if filled_cells(row) > 1 then head:insert(row) end
  end
  if #head == 0 and #el.bodies > 0 then
    local body = el.bodies[1].body
    while #body > 0 and filled_cells(body[1]) <= 1 do body:remove(1) end
    if #body > 0 then head:insert(body:remove(1)) end
  end
  el.head.rows = #head > 0 and {head[#head]} or {}
  return el
end

-- width/height are kept only for absolute CSS length units (\includegraphics
-- also uses cm/mm/in/pt, not just px) or a plain percentage; anything else
-- (e.g. a stray \linewidth the Python side didn't already turn into a
-- percentage) is dropped rather than shown raw.
-- true if `v` is a plain number followed by one of these CSS length units.
local function abs_length(v)
  return v and (v:match("^%d+%.?%d*px$") or v:match("^%d+%.?%d*cm$") or v:match("^%d+%.?%d*mm$")
    or v:match("^%d+%.?%d*in$") or v:match("^%d+%.?%d*pt$"))
end

function pass2.Image(el)
  el.classes = {}
  -- width/height go into a `style` attribute, not bare width=/height=
  -- attributes: the legacy HTML attributes only accept a plain integer
  -- (pixels) - "3cm" fails to parse there and the browser silently falls
  -- back to the image's full intrinsic size, which is why a sized figure
  -- (e.g. \includegraphics[height=3cm]{...}) used to render huge.
  local style = {}
  local width = el.attributes["width"]
  el.attributes["width"] = nil
  if width then
    local frac = width:match("^([%d%.]*)\\%a*width$")
    if frac then
      local n = tonumber(frac) or 1
      if n < 1 then style[#style + 1] = "width:" .. string.format("%d%%", n * 100) end
    elseif width:match("^%d+%%$") then
      style[#style + 1] = "width:" .. width
    elseif abs_length(width) then
      style[#style + 1] = "width:" .. width
    end
  end
  local height = el.attributes["height"]
  el.attributes["height"] = nil
  if abs_length(height) then
    style[#style + 1] = "height:" .. height
  end
  if #style > 0 then
    el.attributes["style"] = table.concat(style, ";")
  end
  return el
end

function pass2.Span(el)
  el.attributes["style"] = nil
  if el.identifier == "" and #el.classes == 0 then
    return el.content
  end
  if el.identifier ~= "" then
    return pandoc.RawInline("html", '<a id="' .. slug(el.identifier) .. '"></a>')
  end
  return el
end

function Pandoc(doc)
  doc = pass1(doc)
  doc = doc:walk(pass2)
  if concepts_out then concepts_out:close() end
  return doc
end
