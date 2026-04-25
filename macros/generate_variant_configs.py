import FreeCAD
import itertools

def get_object_by_user_label(doc, user_label):
    matching_objects = doc.getObjectsByLabel(user_label)
    if matching_objects:
        return matching_objects[0] 
    return None

def generate_variant_combinations():
    doc = FreeCAD.ActiveDocument
    if not doc:
        print("No active document.")
        return

    # --- 1. DEFINE YOUR PARAMETER LISTS HERE ---
    # Edit these lists to contain the values you want to combine.
    # You can use integers, floats, or strings with units (e.g., "15 mm").
    param1_values = [10.1, 10.2]       # Example: Length
    param2_values = [0.3, 0.5, 0.7, 0.9]         # Example: HexIndent
    param3_values = [10]   # HexLength
    
    spreadsheet_label = "VariantData"
    sheet = get_object_by_user_label(doc, spreadsheet_label)

    if not sheet:
        # If the spreadsheet doesn't exist, create it automatically
        sheet = doc.addObject('Spreadsheet::Sheet', 'VariantData')
        sheet.Label = spreadsheet_label
        print(f"Created new spreadsheet: {spreadsheet_label}")

    # --- 2. WRITE SPREADSHEET HEADERS (Row 1) ---
    sheet.set('A1', 'ConfigName')
    sheet.set('B1', 'PipeDiameter')
    sheet.set('C1', 'HexIndent')
    sheet.set('D1', 'HexLength')
    
    # Optional: Make headers bold
    sheet.setStyle('A1:D1', 'bold', 'add')

    # --- 3. GENERATE ALL COMBINATIONS ---
    # itertools.product creates every possible combination of the lists provided
    combinations = list(itertools.product(param1_values, param2_values, param3_values))
    
    print(f"Generating {len(combinations)} total variants...")

    # --- 4. WRITE DATA TO SPREADSHEET ---
    current_row = 2
    for combo in combinations:
        val1, val2, val3 = combo
        
        # Create a unique config name, e.g., "v_10_5.5_3mm"
        # We strip spaces from the generated name to keep it clean
        config_name = f"v_{val1}_{val2}_{val3}".replace(" ", "")
        
        # Write to cells
        sheet.set(f'A{current_row}', f"'{config_name}") # The ' prefix forces FreeCAD to treat it as string
        sheet.set(f'B{current_row}', str(val1))
        sheet.set(f'C{current_row}', str(val2))
        sheet.set(f'D{current_row}', str(val3))
        
        current_row += 1

    # Clear any leftover data below the new list if you ran this previously with more items
    # (Optional, but good practice if you reduce your parameter counts)
    sheet.clear(f'A{current_row}:D1000')

    doc.recompute()
    print("Spreadsheet successfully populated!")

# Run the macro
generate_variant_combinations()
