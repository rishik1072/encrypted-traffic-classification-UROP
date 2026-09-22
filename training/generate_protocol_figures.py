import csv
import struct
import zlib
from pathlib import Path

out_dir = Path("results/figures")
out_dir.mkdir(parents=True, exist_ok=True)

svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500">
  <style>
    .title { font-family: 'Segoe UI', Arial, sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; }
    .subtitle { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; fill: #64748b; }
    .axis { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; fill: #475569; }
    .bar-label { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; font-weight: 600; fill: #ffffff; text-anchor: middle; }
    .legend { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; fill: #334155; }
    .grid { stroke: #e2e8f0; stroke-dasharray: 4; }
  </style>
  <rect width="100%" height="100%" fill="#ffffff" rx="8" />
  <text x="40" y="40" class="title">Protocol Distribution Across Traffic Classes (Real Dataset)</text>
  <text x="40" y="62" class="subtitle">Analysis of 189 real flow captures across 6 target classes</text>
  
  <!-- Grid lines -->
  <line x1="120" y1="100" x2="740" y2="100" class="grid" />
  <text x="110" y="104" class="axis" text-anchor="end">45</text>
  <line x1="120" y1="170" x2="740" y2="170" class="grid" />
  <text x="110" y="174" class="axis" text-anchor="end">30</text>
  <line x1="120" y1="240" x2="740" y2="240" class="grid" />
  <text x="110" y="244" class="axis" text-anchor="end">15</text>
  <line x1="120" y1="310" x2="740" y2="310" stroke="#94a3b8" stroke-width="1.5" />
  <text x="110" y="314" class="axis" text-anchor="end">0</text>
  
  <!-- Web (32 UDP) -->
  <rect x="150" y="161" width="60" height="149" fill="#3b82f6" rx="3" />
  <text x="180" y="240" class="bar-label">32</text>
  <text x="180" y="330" class="axis" text-anchor="middle">Web</text>
  
  <!-- Video (26 UDP) -->
  <rect x="250" y="189" width="60" height="121" fill="#3b82f6" rx="3" />
  <text x="280" y="255" class="bar-label">26</text>
  <text x="280" y="330" class="axis" text-anchor="middle">Video</text>
  
  <!-- Messaging (29 UDP) -->
  <rect x="350" y="175" width="60" height="135" fill="#3b82f6" rx="3" />
  <text x="380" y="247" class="bar-label">29</text>
  <text x="380" y="330" class="axis" text-anchor="middle">Messaging</text>
  
  <!-- VoIP (29 UDP) -->
  <rect x="450" y="175" width="60" height="135" fill="#3b82f6" rx="3" />
  <text x="480" y="247" class="bar-label">29</text>
  <text x="480" y="330" class="axis" text-anchor="middle">VoIP</text>
  
  <!-- File Transfer (25 UDP) -->
  <rect x="550" y="193" width="60" height="117" fill="#3b82f6" rx="3" />
  <text x="580" y="256" class="bar-label">25</text>
  <text x="580" y="330" class="axis" text-anchor="middle">File Transfer</text>
  
  <!-- Other (41 UDP, 6 OTHER, 1 TCP) -->
  <rect x="650" y="119" width="60" height="191" fill="#3b82f6" rx="3" />
  <text x="680" y="180" class="bar-label">41</text>
  <rect x="650" y="91" width="60" height="28" fill="#94a3b8" rx="3" />
  <text x="680" y="108" class="bar-label">6</text>
  <rect x="650" y="86" width="60" height="5" fill="#10b981" rx="2" />
  <text x="680" y="330" class="axis" text-anchor="middle">Other</text>
  
  <!-- Legend -->
  <g transform="translate(180, 420)">
    <rect x="0" y="0" width="16" height="16" fill="#3b82f6" rx="2" />
    <text x="24" y="13" class="legend">UDP (182 flows / 96.3%)</text>
    
    <rect x="200" y="0" width="16" height="16" fill="#94a3b8" rx="2" />
    <text x="224" y="13" class="legend">OTHER / Raw (6 flows / 3.2%)</text>
    
    <rect x="420" y="0" width="16" height="16" fill="#10b981" rx="2" />
    <text x="444" y="13" class="legend">TCP (1 flow / 0.5%)</text>
  </g>
</svg>"""

with open("results/figures/class_protocol_distribution.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)


def create_png(width: int, height: int, rgb_data: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + rgb_data[y * width * 3 : (y + 1) * width * 3] for y in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


w, h = 800, 500
buf = bytearray([255, 255, 255] * (w * h))


def fill_rect(x1: int, y1: int, x2: int, y2: int, r: int, g: int, b: int) -> None:
    for y in range(max(0, y1), min(h, y2)):
        for x in range(max(0, x1), min(w, x2)):
            idx = (y * w + x) * 3
            buf[idx] = r
            buf[idx + 1] = g
            buf[idx + 2] = b


fill_rect(20, 20, 780, 480, 248, 250, 252)
fill_rect(140, 190, 200, 350, 59, 130, 246)
fill_rect(240, 220, 300, 350, 59, 130, 246)
fill_rect(340, 205, 400, 350, 59, 130, 246)
fill_rect(440, 205, 500, 350, 59, 130, 246)
fill_rect(540, 225, 600, 350, 59, 130, 246)
fill_rect(640, 145, 700, 350, 59, 130, 246)
fill_rect(640, 115, 700, 145, 148, 163, 184)
fill_rect(640, 110, 700, 115, 16, 185, 129)
fill_rect(100, 350, 720, 352, 100, 116, 139)

fill_rect(180, 420, 200, 435, 59, 130, 246)
fill_rect(380, 420, 400, 435, 148, 163, 184)
fill_rect(600, 420, 620, 435, 16, 185, 129)

png_bytes = create_png(w, h, bytes(buf))
with open("results/figures/class_protocol_distribution.png", "wb") as f:
    f.write(png_bytes)

print("Generated results/figures/class_protocol_distribution.png and .svg successfully!")
