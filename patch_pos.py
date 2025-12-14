
import os

file_path = r'd:\Project\Workouts\AgencySalesPro-Replit\templates\pos\sale.html'

def get_markers():
    # {{ and }}
    var_start = chr(123) + chr(123)
    var_end = chr(125) + chr(125)
    # {% and %}
    tag_start = chr(123) + chr(37)
    tag_end = chr(37) + chr(125)
    return var_start, var_end, tag_start, tag_end

vs, ve, ts, te = get_markers()

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Try to identify the block boundries
start_marker = "let rawProducts = ["
end_marker = "console.log('POS rawProducts loaded"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    before = content[:start_idx]
    after = content[end_idx:] # Keep the console log line and rest
    
    # Reconstruct the block safely
    block = "let rawProducts = [\n"
    block += "        " + ts + " for p in products " + te + "\n"  # {% for ... %}
    block += "        {\n"
    block += "            id: " + vs + " p.id " + ve + ",\n"    # {{ p.id }}
    block += "            name: " + vs + " (p.name if p.name else '') | tojson " + ve + ",\n"
    block += "            sku: " + vs + " (p.sku if p.sku else '') | tojson " + ve + ",\n"
    block += "            price: " + vs + " p.sell_price or 0 " + ve + ",\n"
    block += "            category: " + vs + " (p.category_ref.name if p.category_ref else 'Other') | tojson " + ve + ",\n"
    block += "            uom: " + vs + " (p.uom_ref.short_name if p.uom_ref else 'pcs') | tojson " + ve + "\n"
    block += "        },\n"
    block += "        " + ts + " endfor " + te + "\n"            # {% endfor %}
    block += "    ];\n    "
    
    final_content = before + block + after
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("Successfully patched rawProducts block with correct tags.")
    
else:
    print("Could not find block boundaries.")

